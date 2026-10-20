# AGENTS.md

Manual for AI agents working on `homeassistant-dlms-cosem`. Read fully before changing code.

## 1. Project Overview

1.1. `homeassistant-dlms-cosem` is a Home Assistant custom component integration for DLMS/COSEM smart electricity meters communicating over serial ports (optical probes, RS-485) or network bridges (TCP/socket).

1.2. Protocol details, state machines, frame handling, retries, and low-level recovery mechanisms belong strictly in the underlying `microdlms` library (located in submodule `microdlms/`). The integration serves strictly as a lean glue layer between Home Assistant and `microdlms`.

1.3. Targeting modern Home Assistant standards (Python 3.14+). Minimum test coverage requirement is 90% branch coverage across `custom_components/dlms_cosem`.

## 2. Tooling & Environment

2.1. Environment and dependencies are managed exclusively with `uv`. Never run bare `pip` or `tox`.

2.2. Common commands:
- `uv sync`: Sync virtual environment with `uv.lock`.
- `uv run prek run --all-files`: Run all git hooks (format, lint, spellcheck, complexity, types).
- `uv run pytest`: Run test suite with branch coverage enforcement (>=90%).
- `uv run python scripts/sync_translations.py --sort`: Sync and sort translations after editing `strings.json`.

## 3. Code Standards & Architecture

3.1. Ruff formats and lints: line length 88, target Python 3.14.

3.2. Cognitive complexity must be at most 15 per function (`complexipy`). Extract private helpers instead of suppressing.

3.3. Timestamps: always use timezone-aware UTC datetimes (`datetime.now(tz=datetime.UTC)`). Never use naive `datetime.now()`.

3.4. Config Entry & Runtime Data:
- Use modern typed config entries: `type DlmsCosemConfigEntry = ConfigEntry[DlmsCoordinator]`.
- Store coordinator directly in `entry.runtime_data = coordinator`.

3.5. Coordinator Lifecycle:
- `DlmsCoordinator` passes `config_entry=connection.entry` to `super().__init__()`, which automatically handles shutdown on unload and stop events.
- Do not add redundant `EVENT_HOMEASSISTANT_STOP` listeners.
- Do not call `coordinator.async_shutdown()` inside `async_unload_entry`.
- `async_unload_entry` must remain a one-liner: `return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)`.

3.6. Hardware Exclusivity in Reconfigure:
- Serial ports and DLMS meter associations are strictly exclusive.
- Because Home Assistant does not unload entries during reconfigure, shut down the active connection before validation:
  `if hasattr(entry, "runtime_data") and entry.runtime_data: await entry.runtime_data.async_shutdown()`

3.7. Slow Links & Attribute Budget:
- Startup: call `coordinator.async_config_entry_first_refresh()` for initial state, and run non-blocking full reads via `hass.async_create_background_task()`.
- Use slow attribute budget (`MAX_SLOW_ATTRIBUTES_PER_POLL = 2`) inside `_async_update_data()` to limit slow entities polled per tick.
- Register attributes with coordinator in `entity.async_added_to_hass()` and unregister in `entity.async_will_remove_from_hass()`.

3.8. Testing:
- Never attempt real serial or network IO; mock `DlmsConnection`, `serialx`, and `microdlms.AsyncMeterClient`.
- Use the `freezer` fixture to advance time when testing coordinator schedules and slow attribute budgets.
- Call `await hass.async_block_till_done()` after config entry operations.

## 4. Git & Commit Conventions

4.1. Feature work must be done on dedicated feature branches (`feature/<feature-name>`).

4.2. Commit message format:
- Always prefix with `[ai] ` (e.g., `[ai] Migrate integration tooling to uv.`).
- Under 50 characters long (including prefix).
- End in a full stop (`.`).

4.3. All commits must have a valid GPG signature (`git commit -S`).

4.4. Verify all checks pass before committing:
- `uv run prek run --all-files`
- `uv run pytest`
