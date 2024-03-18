#!/usr/bin/env python3
"""Updates FLAG IDs database from DLMS UA."""


from collections.abc import Generator
from io import BytesIO
import json
from pathlib import Path
from typing import Final
from urllib.request import urlretrieve

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

URL: Final = "https://www.dlms.com/srv/lib/Export_Flagids.php"
COL: dict[str, int] = {
    "flag_id": 1,
    "manufacturer": 2,
    "country": 3,
    "region": 4,
}

OVERRIDES: dict[str, str] = {
    "KFM": "Shenzhen Kaifa Technology Co., Ltd.",
}


def worksheet_items(ws: Worksheet) -> Generator[tuple[str, str], None, None]:
    """Return flag id and manufacturer tuple from the worksheet."""
    row = 2
    while row < ws.max_row:
        yield (
            ws.cell(row, COL["flag_id"]).value,
            ws.cell(row, COL["manufacturer"]).value,
        )
        row += 1


print("Updating flag ids...")
xlsx_filename, _ = urlretrieve(URL)
with open(xlsx_filename, "rb") as f:
    buffer = BytesIO(f.read())

wb = openpyxl.load_workbook(buffer)
manufacturers = dict(worksheet_items(wb.active))
wb.close()

for flag_id, override in OVERRIDES.items():
    if (manufacturer := manufacturers.get(flag_id, None)) and manufacturer != override:
        manufacturers[flag_id] = override
        print(f'Replaced "{manufacturer}" with "{override}"')

Path("custom_components/dlms_cosem/dlms_flagids.json").write_text(
    json.dumps(manufacturers, indent=2) + "\n"
)
