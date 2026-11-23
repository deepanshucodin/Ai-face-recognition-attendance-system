from datetime import date
from io import BytesIO, StringIO

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from models import Attendance


def attendance_dataframe(start_date=None, end_date=None):
    query = Attendance.query.join(Attendance.student).order_by(Attendance.date.desc(), Attendance.time.desc())
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)

    rows = []
    for record in query.all():
        rows.append(
            {
                "Roll No": record.student.roll_number,
                "Name": record.student.full_name,
                "Date": record.date.isoformat(),
                "Time": record.time.strftime("%H:%M:%S"),
                "Status": record.status,
                "Method": record.method,
            }
        )
    return pd.DataFrame(rows, columns=["Roll No", "Name", "Date", "Time", "Status", "Method"])


def build_csv(start_date=None, end_date=None):
    df = attendance_dataframe(start_date, end_date)
    output = StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()


def build_excel(start_date=None, end_date=None):
    df = attendance_dataframe(start_date, end_date)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attendance")
        summary = pd.DataFrame(
            [
                {"Metric": "Generated Date", "Value": date.today().isoformat()},
                {"Metric": "Present Count", "Value": int((df["Status"] == "PRESENT").sum()) if not df.empty else 0},
                {"Metric": "Absent Count", "Value": int((df["Status"] == "ABSENT").sum()) if not df.empty else 0},
                {"Metric": "Total Records", "Value": len(df)},
            ]
        )
        summary.to_excel(writer, index=False, sheet_name="Summary")

        for sheet_name in ["Attendance", "Summary"]:
            sheet = writer.sheets[sheet_name]
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E79")
            for column_cells in sheet.columns:
                max_length = max(len(str(cell.value or "")) for cell in column_cells)
                sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(max_length + 3, 40)

    output.seek(0)
    return output
