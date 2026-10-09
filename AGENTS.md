# Agent Guidelines for `homeassistant-dlms-cosem`

This document provides context, architectural patterns, and operational rules for AI agents working on this codebase.

---

## 1. Project Overview & Architecture

This repository is a Home Assistant custom component integration for **DLMS/COSEM** smart electricity meters (such as Mercury, Landis+Gyr, etc.) communicating over serial ports (optical probes, RS-485) or network bridges (TCP/socket).

### Tech Stack & Dependencies
- **Home Assistant Core**: Targeting modern HA standards (Python 3.14). Consult https://developers.home-assistant.io/blog/ for important core changes and deprecations that might affect the integration.
- **`dlms-cosem` library**: Upstream library fork (`https://github.com/denpaforks/dlms-cosem`), available locally or as submodule `dlms-cosem/`.
- **`serialx`**: Transport IO backend (`SerialXIO`) supporting standard serial ports (`/dev/ttyUSB*`, `COM*`), network URLs (`socket://`, `tcp://`, `rfc2217://`), and custom Home Assistant schemes (`esphome-hass://`).
- **Data validation**: `probatio` is preferred where specified by lint rules (avoid importing `voluptuous` where banned by `ruff`).

---

## 2. Git & Commit Conventions

- **Commit Message Prefix**: Always prefix agent-generated commits with `[ai]` (e.g., `[ai] Implement slow attribute polling budget`).
- **Commit Message Length and Structure.**: Commit message should be under 50 characters long (including prefix) and end in full stop. (.)
- **Commit Signature**: All commits must have a gpg signature.
- **Branching Strategy**:
  - Feature work must be done on dedicated feature branches (e.g., `feature/<feature-name>`).
  - Do not create temporary fix branches for ongoing refactors; continue work directly on the relevant feature branch.
- **Quality Checks & Pre-commit (`prek`)**:
  This project uses [`prek`](https://github.com/astral-sh/prek) instead of legacy `pre-commit`. Always verify checks pass before committing:
  ```bash
  prek run --all-files
  ```
  Or individual checks as defined in `pyproject.toml` / tox:
  - `prek run ruff-check --all-files` (linting)
  - `prek run ruff-format --all-files` (formatting)
  - `prek run codespell --all-files` (spelling)
  - `prek run check-json --all-files` (JSON validation)
  - `python scripts/sync_translations.py --sort` (sync and sort translations)
  - `pytest` (test suite)
  - `coverage run -m pytest && coverage report` (test coverage, >=90% required)

---

## 3. Home Assistant Architectural Patterns

### 3.1 Config Entry & Runtime Data
- Use modern typed config entries: `type DlmsCosemConfigEntry = ConfigEntry[DlmsCoordinator]`.
- Store the coordinator directly in `entry.runtime_data = coordinator`.

### 3.2 Coordinator Lifecycle & Unload
- `DlmsCoordinator` inherits from `DataUpdateCoordinator`. Passing `config_entry=connection.entry` to `super().__init__()` **automatically** handles:
  - Registering `coordinator.async_shutdown` with `entry.async_on_unload()`.
  - Listening to `EVENT_HOMEASSISTANT_STOP`.
- **Do not** add redundant `EVENT_HOMEASSISTANT_STOP` listeners.
- **Do not** call `coordinator.async_shutdown()` inside `async_unload_entry`.
- `async_unload_entry` should remain a clean one-liner:
  ```python
  async def async_unload_entry(hass: HomeAssistant, entry: DlmsCosemConfigEntry) -> bool:
      """Unload a config entry."""
      return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
  ```

### 3.3 Reconfigure Flow Gotcha (Hardware Exclusivity)
- Unlike normal unloads, Home Assistant **does not unload** an active config entry during `async_step_reconfigure`.
- Because serial ports (`SerialXIO`) and DLMS meter associations are strictly exclusive, the active connection and background polling timer **must be shut down** before validating new credentials in `async_step_reconfigure`:
  ```python
  if hasattr(entry, "runtime_data") and entry.runtime_data:
      await entry.runtime_data.coordinator.async_shutdown()
  ```

---

## 4. Hardware Realities & DLMS Communication

### 4.1 Slow Optical & Serial Links
- DLMS over optical probes is slow (typically 9600 baud; each attribute read takes 0.5–1.5 seconds).
- **Startup Protection**: Do not block Home Assistant startup with heavy attribute reads. Call `coordinator.async_config_entry_first_refresh()` to verify connectivity and initialize state, and run non-blocking full reads via `hass.async_create_background_task()`.

### 4.2 Throttled Entities & "Slow Attribute Budget"
- Entities can define a custom `scan_interval` in their entity descriptions (e.g., 5 minutes or 1 hour for total energy vs. 30 seconds for current active power).
- **Do not use random delays smaller than `DEFAULT_SCAN_INTERVAL`** to stagger requests. Because coordinator execution is quantized to fixed interval ticks (e.g. 30s), sub-cycle random jitter collapses into the same polling tick.
- Use a **slow attribute budget** (`MAX_SLOW_ATTRIBUTES_PER_POLL = 2`) inside `_async_update_data()` to limit how many slow entities are fetched per coordinator cycle. Overdue attributes naturally queue up and spread across subsequent cycles.

### 4.3 Entity UI Control (Approach B)
- Attributes are registered with the coordinator during `entity.async_added_to_hass()` and unregistered in `entity.async_will_remove_from_hass()`.
- This ensures that disabling an entity in the Home Assistant UI stops the coordinator from polling that attribute from the meter, saving precious optical bus bandwidth.

### 4.4 Cryptography & Security Counters
- `client_invocation_counter` in `dlms-cosem` is only incremented during cryptographic ciphering (`security.encrypt`). On standard Low Level Security (LLS) connections, it remains `0`.
- Cyclic fields: HDLC sequence numbers (`client_ssn`, `client_rsn`) are modulo 8 ($0..7$). DLMS invoke IDs are modulo 16 ($0..15$).
- For session statistics and system health, use `DlmsStatistics` on `DlmsClient`.

---

## 5. Coding Standards

- **Timestamps**: Always use timezone-aware UTC datetimes: `datetime.now(tz=datetime.UTC)`. Never use naive `datetime.now()`.
- **Translations**: When modifying `strings.json`, always run:
  ```bash
  python scripts/sync_translations.py --sort
  ```
  to sync changes to `translations/en.json` and `translations/ru.json`.
- **Type Annotations**: Ensure full typing and verify with `mypy custom_components/dlms_cosem tests`.

---

## 6. Test Suite & Testing Patterns

The integration includes an automated test suite located in `tests/`, built upon `pytest-homeassistant-custom-component` and configured via `pyproject.toml`.

### 6.1 Running Tests & Coverage
- **Run the full test suite**:
  ```bash
  pytest
  ```
- **Run tests with coverage**:
  ```bash
  coverage run -m pytest
  coverage report --fail-under=90
  ```
- **Coverage Requirement**: A minimum of 90% branch coverage across `custom_components/dlms_cosem` is enforced (`[tool.coverage.report] fail_under = 90`).
- **Tox Environments**:
  - `tox -e test`: Executes `pytest`.
  - `tox -e coverage`: Executes test coverage report.
  - `tox -e type`: Runs `mypy custom_components/dlms_cosem tests`.

### 6.2 Test Suite Architecture & Fixtures
- `tests/conftest.py`:
  - `auto_enable_custom_integrations`: Autouse fixture enabling custom component loading in the Home Assistant test harness.
  - `mock_config_entry`: Pre-created `MockConfigEntry` populated with standard test configuration and registered with `hass`.
  - `mock_connection`: `MagicMock(spec=DlmsConnection)` simulating active meter connection, statistics (`DlmsStatistics`), and asynchronous calls (`async_connect`, `async_close`, `async_get` matching attributes from `MOCK_COSEM_DATA`).
  - `mock_coordinator`: Pre-initialized `DlmsCoordinator` with populated mock data.
- `tests/const.py`:
  - Contains standardized mock payloads: `MOCK_CONFIG_DATA`, `MOCK_DEVICE_DATA`, `MOCK_ENTRY_DATA`, `MOCK_COSEM_DATA`, and `MOCK_DATETIME`.
- **Test Modules**:
  - `test_init.py`: Component lifecycle, config entry setup/unload, logging level updates via `EVENT_LOGGING_CHANGED`, and entry schema migrations across versions (e.g., minor versions 1 -> 3, 2 -> 3).
  - `test_config_flow.py`: User configuration flows (serial ports with auto-discovery, network sockets), USB discovery flow, auto-baudrate/probe negotiation, reconfigure flow (ensuring active connection shutdown), and error handling (`cannot_connect`, `unknown`).
  - `test_coordinator.py`: First refresh and background non-blocking reads, entity attribute registration/unregistration lifecycle, slow attribute polling budget (`MAX_SLOW_ATTRIBUTES_PER_POLL = 2`), and error handling during polling cycles.
  - `test_dlms_cosem.py`: `DlmsConnection` state machine, transport creation, reconnection and retry loops, LLS authentication, meter identification, and `DlmsStatistics` counters.
  - `test_entity.py`: Base `DlmsEntity` registration, unregistration, availability tracking, and device registry information.
  - `test_sensor.py` & `test_binary_sensor.py`: Platform setups, value scaling/parsing, and tamper/alarm event flag decoding.
  - `test_system_health.py`: Integration diagnostics and system health info callbacks.

### 6.3 Testing Best Practices & Conventions
- **No Real Hardware or Network IO**: Always mock `DlmsConnection`, `serialx.SerialXIO`, and `dlms_cosem.HdlcTransport`. Tests must never attempt to open real serial ports or network sockets.
- **Event Loop Settlement**: Always call `await hass.async_block_till_done()` after config entry operations, state updates, or bus event dispatching.
- **Time Manipulation**: Use the `freezer` fixture (`pytest-freezer`) and `freezer.tick()` / `freezer.move_to()` to advance time when testing coordinator polling schedules and slow attribute budgeting, avoiding real-time sleeps.


