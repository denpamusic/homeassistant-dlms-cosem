#!/usr/bin/env python3
"""Updates FLAG IDs database from DLMS UA."""

import io
import json
from pathlib import Path
from typing import Final
from urllib.request import urlretrieve

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

COL_FLAG_ID: Final = 1
COL_MANUFACTURER: Final = 2

print("Updating the FLAG IDs database...")
xlsx, _ = urlretrieve("https://www.dlms.com/srv/lib/Export_Flagids.php")
with open(xlsx, "rb") as f:
    buffer = io.BytesIO(f.read())

wb = openpyxl.load_workbook(buffer)
ws: Worksheet = wb.active
Path("custom_components/dlms_cosem/dlms_flagids.json").write_text(
    json.dumps(
        {
            ws.cell(row, COL_FLAG_ID).value: ws.cell(row, COL_MANUFACTURER).value
            for row in range(2, ws.max_row)
        },
        indent=2,
    )
)
wb.close()
