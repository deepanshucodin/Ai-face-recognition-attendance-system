from datetime import datetime

from flask import Blueprint, Response, render_template, request, send_file

from services.export_service import build_csv, build_excel
from utils.auth import login_required


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _date_arg(name):
    value = request.args.get(name, "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


@reports_bp.route("/")
@login_required
def reports():
    return render_template("attendance/reports.html")


@reports_bp.route("/csv")
@login_required
def export_csv():
    start_date = _date_arg("start_date")
    end_date = _date_arg("end_date")
    csv_data = build_csv(start_date, end_date)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_report.csv"},
    )


@reports_bp.route("/excel")
@login_required
def export_excel():
    start_date = _date_arg("start_date")
    end_date = _date_arg("end_date")
    output = build_excel(start_date, end_date)
    return send_file(
        output,
        as_attachment=True,
        download_name="attendance_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
