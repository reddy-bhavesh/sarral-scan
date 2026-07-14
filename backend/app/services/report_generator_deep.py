"""
DeepAgentReportGenerator — the report for Deep Agent mode (mode="deep").

Subclasses ReportGenerator to REUSE its styles, charts (pie / gauge / risk matrix),
risk scoring, and footer, but restructures the document around the multi-agent
engagement: an authorization page, a per-specialist coverage matrix, the
orchestrator's delegation timeline, and findings grouped by specialist.

Data sources (richer than the classic report's gemini_summary path):
  - Finding rows   — grouped by `phase` (= specialist name); carry riskScore/CVE/SLA.
  - AgentDecision  — the orchestrator → sub-agent delegation trail.
"""
import html
import json
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app.services.report_generator import ReportGenerator

_SEV_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}


def _g(obj, attr, default=None):
    return getattr(obj, attr, default)


def _norm_sev(sev) -> str:
    s = (sev or "Info").capitalize()
    if s == "Moderate":
        s = "Medium"
    return s if s in _SEV_ORDER else "Info"


class DeepAgentReportGenerator(ReportGenerator):

    def generate_deep_report(self, scan_data, scan_results, findings, decisions,
                             engagement, output_path):
        doc = SimpleDocTemplate(output_path, pagesize=letter,
                                rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=60)
        story = []

        findings = list(findings or [])
        decisions = list(decisions or [])

        # ---- aggregate ----
        vuln_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
        for f in findings:
            vuln_counts[_norm_sev(_g(f, "severity"))] += 1
        total_findings = len(findings)
        risk_score = self._calculate_risk_score(vuln_counts)
        risk_level, risk_color = self._get_risk_level(risk_score)

        # specialist order: from the delegation trail, then any finding-only specialists
        specialist_order = []
        for d in decisions:
            name = _g(d, "afterPhase") or _g(d, "ctemStage")
            if name and name not in specialist_order:
                specialist_order.append(name)
        for f in findings:
            name = _g(f, "phase")
            if name and name not in specialist_order:
                specialist_order.append(name)

        duration = _g(scan_data, "duration_seconds", 0) or 0
        duration_str = f"{duration // 60}m {duration % 60}s" if duration else "N/A"

        # ==================== COVER ====================
        story.append(Spacer(1, 1.6 * inch))
        story.append(Paragraph("SCOUT SECURITY", self.style_title))
        story.append(Paragraph("Deep Agent Penetration Test Report", self.style_subtitle))
        story.append(Paragraph("Multi-Agent Autonomous Assessment",
                               ParagraphStyle('cvtag', fontSize=11, alignment=TA_CENTER,
                                              textColor=self.COLORS['accent'])))
        story.append(Spacer(1, 0.8 * inch))

        target_table = Table([[Paragraph(f"<b>{_g(scan_data, 'target', '')}</b>",
                              ParagraphStyle('Tgt', fontSize=18, alignment=TA_CENTER,
                                             textColor=self.COLORS['primary']))]], colWidths=[400])
        target_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.COLORS['background']),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 15), ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('BOX', (0, 0), (-1, -1), 1, self.COLORS['primary']),
        ]))
        story.append(target_table)
        story.append(Spacer(1, 1.2 * inch))

        org = _g(engagement, "org", "—") if engagement else "—"
        meta = [
            ["Report Date:", datetime.now().strftime('%B %d, %Y')],
            ["Project ID:", f"SCT-DEEP-{_g(scan_data, 'id', 0):04d}"],
            ["Organization:", org],
            ["Scan Duration:", duration_str],
            ["Classification:", "CONFIDENTIAL"],
        ]
        mt = Table(meta, colWidths=[120, 240], hAlign='CENTER')
        mt.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'), ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(mt)
        story.append(PageBreak())

        # ==================== ENGAGEMENT & AUTHORIZATION ====================
        story.append(Paragraph("1. Engagement &amp; Authorization", self.style_h1))
        if engagement:
            in_scope = self._json_list(_g(engagement, "inScope"))
            exclusions = self._json_list(_g(engagement, "exclusions"))
            approver = _g(engagement, "approver") or "—"
            expires = _g(engagement, "expiresAt")
            exp_str = expires.strftime('%Y-%m-%d') if expires else "no expiry"
            auth_rows = [
                [Paragraph("<b>Organization</b>", self.style_small), Paragraph(org, self.style_normal)],
                [Paragraph("<b>In-Scope</b>", self.style_small), Paragraph(", ".join(in_scope) or "—", self.style_normal)],
                [Paragraph("<b>Exclusions</b>", self.style_small), Paragraph(", ".join(exclusions) or "—", self.style_normal)],
                [Paragraph("<b>Approved By</b>", self.style_small), Paragraph(approver, self.style_normal)],
                [Paragraph("<b>Valid Until</b>", self.style_small), Paragraph(exp_str, self.style_normal)],
            ]
            at = Table(auth_rows, colWidths=[90, 390], hAlign='LEFT')
            at.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), self.COLORS['background']),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(at)
        else:
            story.append(Paragraph("Engagement authorization record was not available.", self.style_normal))
        story.append(Spacer(1, 12))
        story.append(Paragraph("Authorization Attestation", self.style_h2))
        story.append(Paragraph(
            "This assessment was performed by Scout's Deep Agent multi-specialist engine ONLY "
            "against the authorized targets listed above. Testing was detection/assessment "
            "oriented. Denial-of-service was evaluated as non-destructive resilience/exposure "
            "assessment only (no flooding). No malware was deployed, no human-targeted social "
            "engineering was performed, and no supply-chain techniques were used. All commands "
            "were validated against the engagement scope before execution.",
            self.style_normal))
        story.append(PageBreak())

        # ==================== EXECUTIVE SUMMARY + RISK ====================
        story.append(Paragraph("2. Executive Summary", self.style_h1))
        crit_high = vuln_counts['Critical'] + vuln_counts['High']
        if crit_high > 0:
            summ = (f"The Deep Agent engagement against <b>{_g(scan_data, 'target', '')}</b> surfaced "
                    f"<b>{total_findings} findings</b>, including <b>{vuln_counts['Critical']} Critical</b> "
                    f"and <b>{vuln_counts['High']} High</b> severity exposures requiring prompt remediation.")
        else:
            summ = (f"The Deep Agent engagement against <b>{_g(scan_data, 'target', '')}</b> surfaced "
                    f"<b>{total_findings} finding(s)</b>, with no Critical or High severity exposures — "
                    f"indicating a reasonable baseline posture for the tested surface.")
        story.append(Paragraph(summ, self.style_normal))
        story.append(Spacer(1, 14))

        # severity counts strip
        counts_data = [
            [str(vuln_counts[s]) for s in ("Critical", "High", "Medium", "Low", "Info")],
            ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
        ]
        ct = Table(counts_data, colWidths=[90] * 5, hAlign='CENTER')
        ct.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 22), ('FONTSIZE', (0, 1), (-1, 1), 8),
            ('TEXTCOLOR', (0, 0), (-1, 1), colors.white),
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS['critical']),
            ('BACKGROUND', (1, 0), (1, -1), self.COLORS['high']),
            ('BACKGROUND', (2, 0), (2, -1), self.COLORS['medium']),
            ('BACKGROUND', (3, 0), (3, -1), self.COLORS['low']),
            ('BACKGROUND', (4, 0), (4, -1), self.COLORS['info']),
            ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(ct)
        story.append(Spacer(1, 20))
        story.append(Paragraph("Overall Risk", self.style_h2))
        story.append(Table([[self._create_risk_gauge(risk_score)]], hAlign='CENTER'))
        story.append(Spacer(1, 10))
        story.append(Table([[self._create_pie_chart(vuln_counts)]], hAlign='CENTER'))
        story.append(PageBreak())

        # ==================== SPECIALIST COVERAGE ====================
        story.append(Paragraph("3. Specialist Agent Coverage", self.style_h1))
        story.append(Paragraph(
            "Each specialist sub-agent is proficient in a single attack type. The orchestrator "
            "delegated to the agents below; this matrix shows what each engaged and found.",
            self.style_normal))
        story.append(Spacer(1, 10))

        cov_header = ["Specialist (Attack Type)", "Cmds", "C", "H", "M", "L", "I"]
        cov_data = [cov_header]
        for name in specialist_order:
            cmds = sum(1 for d in decisions
                       if (_g(d, "afterPhase") or _g(d, "ctemStage")) == name and _g(d, "authoredCommand"))
            sev_local = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
            for f in findings:
                if _g(f, "phase") == name:
                    sev_local[_norm_sev(_g(f, "severity"))] += 1
            cov_data.append([
                Paragraph(name, self.style_small), str(cmds),
                str(sev_local["Critical"]), str(sev_local["High"]),
                str(sev_local["Medium"]), str(sev_local["Low"]), str(sev_local["Info"]),
            ])
        if len(cov_data) == 1:
            cov_data.append([Paragraph("No specialists engaged.", self.style_small), "0", "0", "0", "0", "0", "0"])
        cov = Table(cov_data, colWidths=[250, 45, 30, 30, 30, 30, 30], hAlign='LEFT')
        cov.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.COLORS['background']]),
        ]))
        story.append(cov)
        story.append(Paragraph("<i>C=Critical, H=High, M=Medium, L=Low, I=Info</i>",
                               ParagraphStyle('cap', fontSize=8, textColor=self.COLORS['text_light'])))
        story.append(PageBreak())

        # ==================== DECISION TIMELINE ====================
        story.append(Paragraph("4. Orchestrator Decision Timeline", self.style_h1))
        story.append(Paragraph(
            "The orchestrator's delegation trail — each step it tasked a specialist and the "
            "command that specialist ran.", self.style_normal))
        story.append(Spacer(1, 10))
        steps = [d for d in decisions if _g(d, "authoredCommand")]
        if not steps:
            story.append(Paragraph("No tool-running steps were recorded.", self.style_normal))
        else:
            tl = [["#", "Specialist", "Command / Reasoning"]]
            for i, d in enumerate(steps, 1):
                name = _g(d, "afterPhase") or _g(d, "ctemStage") or "—"
                cmd = html.escape((_g(d, "authoredCommand") or "")[:160])
                reason = html.escape((_g(d, "reasoning") or "")[:200])
                cell = Paragraph(f"<font name='Courier' size='7'>{cmd}</font><br/>"
                                 f"<font size='8' color='#4a5568'>{reason}</font>", self.style_normal)
                tl.append([str(i), Paragraph(name, self.style_small), cell])
            tlt = Table(tl, colWidths=[24, 130, 326], hAlign='LEFT')
            tlt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS['secondary']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(tlt)
        story.append(PageBreak())

        # ==================== FINDINGS BY SPECIALIST ====================
        story.append(Paragraph("5. Findings by Specialist", self.style_h1))
        if not findings:
            story.append(Paragraph("No findings were identified during this assessment.", self.style_normal))
        else:
            for name in specialist_order:
                group = [f for f in findings if _g(f, "phase") == name]
                if not group:
                    continue
                group.sort(key=lambda f: _SEV_ORDER.get(_norm_sev(_g(f, "severity")), 5))
                story.append(Paragraph(f"{name} ({len(group)})", self.style_h2))
                for f in group:
                    story.append(self._finding_card(f))   # each card is its own KeepTogether
                    story.append(Spacer(1, 8))
                story.append(Spacer(1, 6))

        # ==================== REMEDIATION PRIORITIES ====================
        story.append(PageBreak())
        story.append(Paragraph("6. Remediation Priorities", self.style_h1))
        prioritized = sorted(
            findings,
            key=lambda f: (-(_g(f, "riskScore") or 0), _SEV_ORDER.get(_norm_sev(_g(f, "severity")), 5)),
        )[:15]
        if not prioritized:
            story.append(Paragraph("No remediation items.", self.style_normal))
        else:
            pr = [["#", "Finding", "Severity", "Risk", "SLA Due"]]
            for i, f in enumerate(prioritized, 1):
                sla = _g(f, "slaDueDate")
                sla_str = sla.strftime('%Y-%m-%d') if sla else "—"
                rs = _g(f, "riskScore")
                pr.append([
                    str(i), Paragraph((_g(f, "title") or "Issue")[:60], self.style_small),
                    _norm_sev(_g(f, "severity")),
                    (f"{rs:.0f}" if rs is not None else "—"), sla_str,
                ])
            prt = Table(pr, colWidths=[24, 270, 70, 45, 71], hAlign='LEFT')
            prt.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS['primary']),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            for r in range(1, len(pr)):
                bg = self.SEVERITY_COLORS.get(pr[r][2], self.COLORS['info'])
                prt.setStyle(TableStyle([('BACKGROUND', (2, r), (2, r), bg),
                                         ('TEXTCOLOR', (2, r), (2, r), colors.white)]))
            story.append(prt)

        # ==================== METHODOLOGY & SAFETY ====================
        story.append(Spacer(1, 20))
        story.append(Paragraph("7. Methodology &amp; Safety", self.style_h2))
        story.append(Paragraph(
            "Specialists deployed: " + (", ".join(specialist_order) or "none") + ". Every command "
            "was a developer-authored template with validated parameters, gated against the "
            "engagement scope before execution. DoS was assessed non-destructively; brute-force "
            "(where used) was rate-limited and lockout-aware. Excluded by policy: DoS attacks, "
            "malware, social engineering, and supply-chain compromise.",
            self.style_normal))

        target = _g(scan_data, "target", "")
        doc.build(story, onFirstPage=lambda c, d: self._add_footer(c, d, target),
                  onLaterPages=lambda c, d: self._add_footer(c, d, target))
        return output_path

    # ------------------------------------------------------------------ #
    @staticmethod
    def _json_list(raw):
        try:
            v = json.loads(raw) if isinstance(raw, str) else (raw or [])
            return [str(x) for x in v] if isinstance(v, list) else []
        except Exception:
            return []

    def _finding_card(self, f):
        """A compact detail card for one Finding row."""
        sev = _norm_sev(_g(f, "severity"))
        sev_color = self.SEVERITY_COLORS.get(sev, self.COLORS['info'])
        title = _g(f, "title") or "Issue"
        header = Table([[
            Paragraph(f"<b>{html.escape(title)}</b>", self.style_h3),
            Paragraph(f"<font color='white'><b>{sev.upper()}</b></font>",
                      ParagraphStyle('b', fontSize=9, alignment=TA_CENTER)),
        ]], colWidths=[400, 80])
        header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('BACKGROUND', (1, 0), (1, 0), sev_color),
            ('TOPPADDING', (1, 0), (1, 0), 6), ('BOTTOMPADDING', (1, 0), (1, 0), 6),
        ]))

        refs = []
        if _g(f, "owasp"):
            refs.append(f"OWASP: {_g(f, 'owasp')}")
        if _g(f, "cwe"):
            refs.append(f"CWE: {_g(f, 'cwe')}")
        if _g(f, "cveId"):
            refs.append(f"CVE: {_g(f, 'cveId')}")
        rows = [
            [Paragraph("<b>Description</b>", self.style_small),
             Paragraph(html.escape((_g(f, "description") or "—"))[:1200], self.style_normal)],
            [Paragraph("<b>Tool</b>", self.style_small),
             Paragraph(_g(f, "tool") or "—", self.style_normal)],
            [Paragraph("<b>References</b>", self.style_small),
             Paragraph(" | ".join(refs) or "N/A", self.style_small)],
            [Paragraph("<b>Remediation</b>", self.style_small),
             Paragraph(html.escape((_g(f, "remediation") or "—"))[:800], self.style_normal)],
        ]
        ev = _g(f, "evidence")
        if ev:
            rows.append([Paragraph("<b>Evidence</b>", self.style_small),
                         Paragraph(f"<font name='Courier' size='7'>{html.escape(str(ev))[:400]}</font>",
                                   self.style_normal)])
        t = Table(rows, colWidths=[80, 400], hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS['background']),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS['background']),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        return KeepTogether([header, Spacer(1, 6), t])
