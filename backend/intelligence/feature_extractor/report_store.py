"""
Persistence layer for CTI investigation reports.

Kept separate from report.py (the generation logic) so that HOW a report is
generated never has to know or care about HOW it's stored. main.py wires the
two together.
"""
import datetime
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .models import InvestigationReport


def save_report(
    db: Session,
    domain_id: str,
    page_id: str,
    page_url: str,
    page_name: str,
    report: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Persist a generated report to Postgres and return it with its new
    report_id + generated_at attached, so the caller can hand that straight
    back to the frontend.

    Defensive by design: report.py's exact return shape isn't fixed here, so
    we pull out `summary` / `risk_level` / `features` if present but never
    fail the request if they aren't — the full report always goes into
    report_json regardless.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    report_id = uuid.uuid4()

    summary = ""
    risk_level = None
    feature_count = 0
    if isinstance(report, dict):
        summary = (report.get("summary") or report.get("executive_summary") or "")[:5000] \
            if isinstance(report.get("summary") or report.get("executive_summary"), str) else ""
        risk_level = report.get("risk_level") or report.get("risk_assessment")
        if not isinstance(risk_level, str):
            risk_level = None
        feats = report.get("features") or report.get("indicators") or []
        feature_count = len(feats) if isinstance(feats, list) else 0

    record = InvestigationReport(
        report_id=report_id,
        domain_id=domain_id,
        page_id=page_id,
        page_url=page_url or "",
        page_name=page_name or "",
        report_json=report,
        summary=summary,
        risk_level=risk_level,
        feature_count=feature_count,
        generated_at=now,
    )

    try:
        db.add(record)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[ReportStore] Failed to persist report: {type(e).__name__}: {str(e)[:200]}")
        # Don't fail the API call just because storage failed — the analyst
        # still gets their report, we just log the storage miss.
        report_out = dict(report) if isinstance(report, dict) else {"report": report}
        report_out["report_id"] = str(report_id)
        report_out["generated_at"] = now.isoformat()
        report_out["persisted"] = False
        return report_out

    report_out = dict(report) if isinstance(report, dict) else {"report": report}
    report_out["report_id"] = str(report_id)
    report_out["generated_at"] = now.isoformat()
    report_out["persisted"] = True
    return report_out


def get_report_history(
    db: Session,
    domain_id: Optional[str] = None,
    page_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Fetch past reports for a page or domain, most recent first."""
    query = db.query(InvestigationReport)
    if domain_id:
        query = query.filter(InvestigationReport.domain_id == domain_id)
    if page_id:
        query = query.filter(InvestigationReport.page_id == page_id)

    records = query.order_by(InvestigationReport.generated_at.desc()).limit(limit).all()

    return [
        {
            "report_id": str(r.report_id),
            "domain_id": str(r.domain_id) if r.domain_id else None,
            "page_id": str(r.page_id) if r.page_id else None,
            "page_url": r.page_url,
            "page_name": r.page_name,
            "summary": r.summary,
            "risk_level": r.risk_level,
            "feature_count": r.feature_count,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "report_json": r.report_json,
        }
        for r in records
    ]
