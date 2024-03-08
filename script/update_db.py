#!/usr/bin/env python3
"""Updates FLAG IDs database from DLMS UA."""


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

print("Updating flag ids...")
xlsx_filename, _ = urlretrieve(URL)
with open(xlsx_filename, "rb") as f:
    buffer = BytesIO(f.read())

wb = openpyxl.load_workbook(buffer)
ws: Worksheet = wb.active
Path("custom_components/dlms_cosem/dlms_flagids.json").write_text(
    json.dumps(
        {
            ws.cell(row, COL["flag_id"]).value: ws.cell(row, COL["manufacturer"]).value
            for row in range(2, ws.max_row)
        },
        indent=2,
    )
)
wb.close()
