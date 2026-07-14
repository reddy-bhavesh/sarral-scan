from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Circle
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from datetime import datetime
import json
import html
import os
import io


class ReportGenerator:
    """Enhanced PDF Report Generator with professional styling and charts."""
    
    # Color Palette - Modern Professional
    COLORS = {
        'primary': colors.HexColor('#1a365d'),      # Dark blue
        'secondary': colors.HexColor('#2c5282'),    # Medium blue
        'accent': colors.HexColor('#3182ce'),       # Accent blue
        'critical': colors.HexColor('#c53030'),     # Red
        'high': colors.HexColor('#dd6b20'),         # Orange
        'medium': colors.HexColor('#d69e2e'),       # Yellow/Gold
        'low': colors.HexColor('#38a169'),          # Green
        'info': colors.HexColor('#3182ce'),         # Blue
        'text': colors.HexColor('#1a202c'),         # Dark gray
        'text_light': colors.HexColor('#4a5568'),   # Medium gray
        'background': colors.HexColor('#f7fafc'),   # Light gray
        'white': colors.white,
        'black': colors.black,
    }
    
    SEVERITY_COLORS = {
        'Critical': COLORS['critical'],
        'High': COLORS['high'],
        'Medium': COLORS['medium'],
        'Low': COLORS['low'],
        'Info': COLORS['info'],
    }

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """Create custom paragraph styles."""
        self.style_title = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Title'],
            fontName='Helvetica-Bold',
            fontSize=28,
            textColor=self.COLORS['primary'],
            alignment=TA_CENTER,
            spaceAfter=12
        )
        
        self.style_subtitle = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=14,
            textColor=self.COLORS['text_light'],
            alignment=TA_CENTER,
            spaceAfter=6
        )
        
        self.style_h1 = ParagraphStyle(
            'CustomH1',
            parent=self.styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=18,
            textColor=self.COLORS['primary'],
            spaceBefore=20,
            spaceAfter=12,
            borderWidth=0,
            borderPadding=0,
            borderColor=self.COLORS['primary'],
            borderRadius=None,
        )
        
        self.style_h2 = ParagraphStyle(
            'CustomH2',
            parent=self.styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=self.COLORS['secondary'],
            spaceBefore=15,
            spaceAfter=8
        )
        
        self.style_h3 = ParagraphStyle(
            'CustomH3',
            parent=self.styles['Heading3'],
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=self.COLORS['text'],
            spaceBefore=10,
            spaceAfter=6
        )
        
        self.style_normal = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=self.COLORS['text'],
            leading=14,
            alignment=TA_LEFT
        )
        
        self.style_small = ParagraphStyle(
            'CustomSmall',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            textColor=self.COLORS['text_light'],
            leading=12
        )
        
        self.style_code = ParagraphStyle(
            'CustomCode',
            parent=self.styles['Code'],
            fontName='Courier',
            fontSize=8,
            backColor=colors.HexColor('#edf2f7'),
            borderPadding=8,
            leading=10
        )

    @staticmethod
    def _rl(text) -> str:
        """Escape free-text (AI/tool output) for ReportLab's Paragraph mini-markup.
        Without this, content like '<link ... rel="stylesheet">' or a bare '&' is
        parsed as markup and raises a paraparser syntax error, crashing the report."""
        return html.escape(str(text if text is not None else ""), quote=False)

    def _create_pie_chart(self, vuln_counts, width=400, height=250):
        """Create a pie chart showing vulnerability distribution."""
        drawing = Drawing(width, height)
        
        # Filter out zero counts
        data = []
        labels = []
        chart_colors = []
        
        for severity in ['Critical', 'High', 'Medium', 'Low', 'Info']:
            count = vuln_counts.get(severity, 0)
            if count > 0:
                data.append(count)
                labels.append(f"{severity}: {count}")
                chart_colors.append(self.SEVERITY_COLORS[severity])
        
        if not data:
            # No vulnerabilities - show empty state
            drawing.add(String(width/2, height/2, "No vulnerabilities found", 
                              textAnchor='middle', fontSize=12, fillColor=self.COLORS['text_light']))
            return drawing
        
        pie = Pie()
        pie.x = width/2 - 75  # Center the pie
        pie.y = 40
        pie.width = 150
        pie.height = 150
        pie.data = data
        pie.labels = labels
        pie.slices.strokeWidth = 2
        pie.slices.strokeColor = colors.white
        
        for i, color in enumerate(chart_colors):
            pie.slices[i].fillColor = color
            pie.slices[i].popout = 5 if i == 0 else 0  # Pop out the first (most critical)
        
        pie.sideLabels = True
        pie.simpleLabels = False
        pie.slices.fontName = 'Helvetica-Bold'
        pie.slices.fontSize = 10
        
        drawing.add(pie)
        return drawing

    def _calculate_risk_score(self, vuln_counts):
        """Calculate an overall risk score (0-100) using a more realistic formula.
        
        Uses a diminishing returns approach - each additional vulnerability of the
        same severity contributes less to the overall score. This prevents
        inflated scores from many low-severity findings.
        
        Baseline scores (first occurrence):
        - Critical: 30 points
        - High: 15 points
        - Medium: 5 points
        - Low: 1 point
        - Info: 0 points
        
        Each additional finding of same severity adds 50% of the previous increment.
        """
        base_scores = {'Critical': 30, 'High': 15, 'Medium': 5, 'Low': 1, 'Info': 0}
        total_score = 0
        
        for severity, count in vuln_counts.items():
            base = base_scores.get(severity, 0)
            if base == 0 or count == 0:
                continue
            
            # Diminishing returns: first vuln = base, second = base*0.5, third = base*0.25, etc.
            severity_score = 0
            for i in range(count):
                severity_score += base * (0.5 ** i)
            
            total_score += severity_score
        
        # Cap at 100
        return min(100, round(total_score))

    def _get_risk_level(self, score):
        """Get risk level text and color based on score."""
        if score >= 80:
            return "Critical Risk", self.COLORS['critical']
        elif score >= 55:
            return "High Risk", self.COLORS['high']
        elif score >= 30:
            return "Medium Risk", self.COLORS['medium']
        elif score > 0:
            return "Low Risk", self.COLORS['low']
        else:
            return "Minimal Risk", self.COLORS['info']

    def _create_risk_gauge(self, score, width=400, height=100):
        """Create a visual risk gauge."""
        drawing = Drawing(width, height)
        
        # Background bar - centered
        bar_width = 350
        bar_height = 30
        bar_x = (width - bar_width) / 2
        bar_y = 50
        
        # Gradient background (segments)
        segment_width = bar_width / 4
        segments = [
            (self.COLORS['low'], 0),
            (self.COLORS['medium'], 1),
            (self.COLORS['high'], 2),
            (self.COLORS['critical'], 3),
        ]
        
        for color, i in segments:
            rect = Rect(bar_x + i * segment_width, bar_y, segment_width, bar_height)
            rect.fillColor = color
            rect.strokeColor = None
            drawing.add(rect)
        
        # Score indicator
        indicator_x = bar_x + (score / 100) * bar_width
        indicator = Circle(indicator_x, bar_y + bar_height/2, 10)
        indicator.fillColor = colors.white
        indicator.strokeColor = self.COLORS['primary']
        indicator.strokeWidth = 3
        drawing.add(indicator)
        
        # Score text
        level_text, level_color = self._get_risk_level(score)
        drawing.add(String(width/2, 15, f"{level_text} ({score}/100)", 
                          textAnchor='middle', fontSize=14, fontName='Helvetica-Bold',
                          fillColor=level_color))
        
        return drawing

    def _create_risk_matrix(self, score, width=350, height=200):
        """Create a 5x5 risk matrix showing Likelihood vs Impact."""
        drawing = Drawing(width, height)
        
        # Matrix dimensions
        cell_size = 30
        matrix_x = 80
        matrix_y = 30
        
        # Color gradient for risk levels (5x5 matrix)
        # Rows: Likelihood (bottom to top: Very Low to Very High)
        # Cols: Impact (left to right: Negligible to Critical)
        risk_colors = [
            # Row 0 (Very Low Likelihood)
            [colors.HexColor('#3182ce'), colors.HexColor('#3182ce'), colors.HexColor('#38a169'), colors.HexColor('#38a169'), colors.HexColor('#d69e2e')],
            # Row 1 (Low)
            [colors.HexColor('#3182ce'), colors.HexColor('#38a169'), colors.HexColor('#38a169'), colors.HexColor('#d69e2e'), colors.HexColor('#d69e2e')],
            # Row 2 (Medium)
            [colors.HexColor('#38a169'), colors.HexColor('#38a169'), colors.HexColor('#d69e2e'), colors.HexColor('#d69e2e'), colors.HexColor('#dd6b20')],
            # Row 3 (High)
            [colors.HexColor('#38a169'), colors.HexColor('#d69e2e'), colors.HexColor('#d69e2e'), colors.HexColor('#dd6b20'), colors.HexColor('#c53030')],
            # Row 4 (Very High Likelihood)
            [colors.HexColor('#d69e2e'), colors.HexColor('#d69e2e'), colors.HexColor('#dd6b20'), colors.HexColor('#c53030'), colors.HexColor('#c53030')],
        ]
        
        # Draw matrix cells
        for row in range(5):
            for col in range(5):
                x = matrix_x + col * cell_size
                y = matrix_y + row * cell_size
                rect = Rect(x, y, cell_size, cell_size)
                rect.fillColor = risk_colors[row][col]
                rect.strokeColor = colors.white
                rect.strokeWidth = 1
                drawing.add(rect)
        
        # Calculate position based on score (0-100 maps to 5x5 grid)
        # Simple mapping: score determines position
        if score >= 80:
            pos_row, pos_col = 4, 4  # Critical
        elif score >= 55:
            pos_row, pos_col = 3, 3  # High
        elif score >= 30:
            pos_row, pos_col = 2, 2  # Medium
        elif score > 0:
            pos_row, pos_col = 1, 1  # Low
        else:
            pos_row, pos_col = 0, 0  # Minimal
        
        # Draw position indicator
        ind_x = matrix_x + pos_col * cell_size + cell_size/2
        ind_y = matrix_y + pos_row * cell_size + cell_size/2
        indicator = Circle(ind_x, ind_y, 8)
        indicator.fillColor = colors.white
        indicator.strokeColor = colors.black
        indicator.strokeWidth = 2
        drawing.add(indicator)
        
        # Y-axis label (Likelihood)
        drawing.add(String(25, matrix_y + 2.5*cell_size, "Likelihood", 
                          textAnchor='middle', fontSize=9, fontName='Helvetica-Bold',
                          fillColor=self.COLORS['text']))
        
        # X-axis label (Impact)
        drawing.add(String(matrix_x + 2.5*cell_size, 12, "Impact",
                          textAnchor='middle', fontSize=9, fontName='Helvetica-Bold',
                          fillColor=self.COLORS['text']))
        
        # Legend
        legend_x = matrix_x + 5*cell_size + 15
        legend_items = [
            ("Critical", colors.HexColor('#c53030')),
            ("High", colors.HexColor('#dd6b20')),
            ("Medium", colors.HexColor('#d69e2e')),
            ("Low", colors.HexColor('#38a169')),
            ("Minimal", colors.HexColor('#3182ce')),
        ]
        for i, (label, color) in enumerate(legend_items):
            y = matrix_y + (4-i) * 28
            rect = Rect(legend_x, y, 15, 15)
            rect.fillColor = color
            rect.strokeColor = None
            drawing.add(rect)
            drawing.add(String(legend_x + 20, y + 4, label, fontSize=8, fillColor=self.COLORS['text']))
        
        return drawing

    def _add_footer(self, canvas, doc, target):
        """Add footer and watermark to each page."""
        canvas.saveState()
        
        # ===== WATERMARK =====
        canvas.setFillColor(colors.Color(0, 0, 0, alpha=0.04))  # Very light gray
        canvas.setFont('Helvetica-Bold', 60)
        
        # Rotate and draw watermark in center
        canvas.translate(letter[0]/2, letter[1]/2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, "CONFIDENTIAL")
        canvas.rotate(-45)
        canvas.translate(-letter[0]/2, -letter[1]/2)
        
        # ===== FOOTER =====
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(self.COLORS['text_light'])
        
        # Footer line
        canvas.setStrokeColor(self.COLORS['background'])
        canvas.line(50, 45, letter[0]-50, 45)
        
        # Footer text
        canvas.drawString(50, 32, f"Target: {target}")
        canvas.drawCentredString(letter[0]/2, 32, "CONFIDENTIAL")
        canvas.drawRightString(letter[0]-50, 32, f"Page {doc.page}")

        # Attribution line
        canvas.setFont('Helvetica', 7)
        canvas.drawCentredString(letter[0]/2, 21, "Created by Scout")

        canvas.restoreState()

    def generate_report(self, scan_data, scan_results, output_path):
        """Generate an enhanced PDF report."""
        doc = SimpleDocTemplate(
            output_path, 
            pagesize=letter,
            rightMargin=50, 
            leftMargin=50,
            topMargin=50, 
            bottomMargin=60
        )
        
        story = []
        
        # --- Process Data ---
        all_vulns = []
        vuln_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
        categories = {}  # Group by tool/category
        
        for result in scan_results:
            if result.gemini_summary:
                try:
                    data = json.loads(result.gemini_summary)
                    if "vulnerabilities" in data:
                        for v in data["vulnerabilities"]:
                            if not v.get('Tool'):
                                v['Tool'] = result.tool
                            
                            # Normalize severity
                            sev = v.get("Severity", "Info").capitalize()
                            if sev == "Moderate": 
                                sev = "Medium"
                            if sev not in vuln_counts: 
                                sev = "Info"
                            v['Severity'] = sev
                            
                            all_vulns.append(v)
                            vuln_counts[sev] += 1
                            
                            # Group by category (tool)
                            tool = v.get('Tool', 'Other')
                            if tool not in categories:
                                categories[tool] = []
                            categories[tool].append(v)
                except:
                    pass
        
        # Sort by severity
        sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
        all_vulns.sort(key=lambda x: sev_order.get(x['Severity'], 5))
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(vuln_counts)
        risk_level, risk_color = self._get_risk_level(risk_score)
        
        # Calculate scan duration - use stored value or calculate from timestamps
        scan_duration = getattr(scan_data, 'duration_seconds', 0) or 0
        if scan_duration > 0:
            duration_str = f"{scan_duration // 60}m {scan_duration % 60}s"
        else:
            # If no duration stored, show time since scan started
            try:
                from datetime import timezone
                scan_date = scan_data.date
                if scan_date:
                    elapsed = (datetime.now(timezone.utc) - scan_date.replace(tzinfo=timezone.utc)).total_seconds()
                    if elapsed > 0:
                        duration_str = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
                    else:
                        duration_str = "< 1m"
                else:
                    duration_str = "N/A"
            except:
                duration_str = "N/A"

        # ==================== COVER PAGE ====================
        story.append(Spacer(1, 1.5*inch))
        
        # Shield Logo using ReportLab drawing
        from reportlab.graphics.shapes import Path
        
        logo_size = 60
        logo_drawing = Drawing(logo_size, logo_size)
        
        # Blue rounded background
        bg_rect = Rect(0, 0, logo_size, logo_size, rx=8, ry=8)
        bg_rect.fillColor = self.COLORS['accent']
        bg_rect.strokeColor = None
        logo_drawing.add(bg_rect)
        
        # Shield outline (white) - drawn as a path
        # Shield shape: starts at top center, curves down on both sides to a point at bottom
        shield_path = Path()
        cx, cy = logo_size / 2, logo_size / 2 + 5  # Center point, shifted up slightly
        sw, sh = 24, 28  # Shield width and height
        
        # Draw shield shape
        shield_path.moveTo(cx, cy + sh/2 - 4)  # Bottom point
        shield_path.lineTo(cx - sw/2, cy + sh/4)  # Bottom left
        shield_path.lineTo(cx - sw/2, cy - sh/4)  # Top left  
        shield_path.curveTo(cx - sw/2, cy - sh/2, cx - sw/4, cy - sh/2, cx, cy - sh/2)  # Top curve left
        shield_path.curveTo(cx + sw/4, cy - sh/2, cx + sw/2, cy - sh/2, cx + sw/2, cy - sh/4)  # Top curve right
        shield_path.lineTo(cx + sw/2, cy + sh/4)  # Top right
        shield_path.closePath()
        
        shield_path.fillColor = None
        shield_path.strokeColor = colors.white
        shield_path.strokeWidth = 2.5
        logo_drawing.add(shield_path)
        
        # Center the logo
        logo_table_data = [[logo_drawing]]
        logo_table = Table(logo_table_data, colWidths=[logo_size], hAlign='CENTER')
        story.append(logo_table)
        story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph("SCOUT SECURITY", self.style_title))
        story.append(Paragraph("Vulnerability Assessment Report", self.style_subtitle))
        
        story.append(Spacer(1, 1*inch))
        
        # Target info box
        target_data = [
            [Paragraph(f"<b>{self._rl(scan_data.target)}</b>", ParagraphStyle('Target', fontSize=18, alignment=TA_CENTER, textColor=self.COLORS['primary']))]
        ]
        target_table = Table(target_data, colWidths=[400])
        target_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), self.COLORS['background']),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('TOPPADDING', (0,0), (-1,-1), 15),
            ('BOTTOMPADDING', (0,0), (-1,-1), 15),
            ('BOX', (0,0), (-1,-1), 1, self.COLORS['primary']),
        ]))
        story.append(target_table)
        
        story.append(Spacer(1, 1.5*inch))
        
        # Report metadata
        meta_data = [
            ["Report Date:", datetime.now().strftime('%B %d, %Y')],
            ["Project ID:", f"SCT-{scan_data.id:04d}"],
            ["Scan Duration:", duration_str],
            ["Classification:", "CONFIDENTIAL"],
        ]
        meta_table = Table(meta_data, colWidths=[120, 200], hAlign='CENTER')
        meta_table.setStyle(TableStyle([
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('TEXTCOLOR', (0,0), (-1,-1), self.COLORS['text']),
            ('ALIGN', (0,0), (0,-1), 'RIGHT'),
            ('ALIGN', (1,0), (1,-1), 'LEFT'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(meta_table)
        
        story.append(PageBreak())

        # ==================== TABLE OF CONTENTS ====================
        story.append(Paragraph("Table of Contents", self.style_h1))
        story.append(Spacer(1, 10))
        
        toc_items = [
            ("1. Executive Summary", 3),
            ("2. Risk Overview", 3),
            ("3. Vulnerability Summary", 4),
            ("4. Detailed Findings", 5),
            ("5. Remediation Priorities", "—"),
        ]
        
        toc_data = []
        for item, page in toc_items:
            toc_data.append([
                Paragraph(item, self.style_normal),
                Paragraph(str(page), ParagraphStyle('TOCPage', fontSize=10, alignment=TA_RIGHT))
            ])
        
        toc_table = Table(toc_data, colWidths=[400, 50])
        toc_table.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 0.5, self.COLORS['background']),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(toc_table)
        
        story.append(Spacer(1, 30))
        
        # ==================== FINDING SEVERITY RATINGS ====================
        story.append(Paragraph("Finding Severity Ratings", self.style_h1))
        story.append(Paragraph(
            "The following table defines levels of severity and corresponding CVSS score range used throughout the document.",
            self.style_normal
        ))
        story.append(Spacer(1, 10))
        
        # Severity definitions data
        severity_definitions = [
            ("Critical", "9.0-10.0", "Exploitation is straightforward and usually results in system-level compromise."),
            ("High", "7.0-8.9", "Exploitation is more difficult but could cause elevated privileges and data loss."),
            ("Medium", "4.0-6.9", "Vulnerabilities exist but are not exploitable or require extra steps."),
            ("Low", "0.1-3.9", "Vulnerabilities are non-exploitable but reduce attack surface."),
            ("Info", "N/A", "No vulnerability exists. Additional information provided."),
        ]
        
        # Build table data
        sev_table_data = [["Severity", "CVSS V3 Range", "Definition"]]
        for sev, cvss, definition in severity_definitions:
            sev_table_data.append([
                sev,
                cvss,
                Paragraph(definition, self.style_small)
            ])
        
        sev_table = Table(sev_table_data, colWidths=[80, 80, 340], hAlign='LEFT')
        sev_table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0,0), (-1,0), self.COLORS['primary']),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 10),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            # Grid
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            # Severity column colors
            ('BACKGROUND', (0,1), (0,1), self.COLORS['critical']),
            ('BACKGROUND', (0,2), (0,2), self.COLORS['high']),
            ('BACKGROUND', (0,3), (0,3), self.COLORS['medium']),
            ('BACKGROUND', (0,4), (0,4), self.COLORS['low']),
            ('BACKGROUND', (0,5), (0,5), self.COLORS['info']),
            ('TEXTCOLOR', (0,1), (0,5), colors.white),
            ('FONTNAME', (0,1), (0,5), 'Helvetica-Bold'),
            ('ALIGN', (0,1), (1,5), 'CENTER'),
        ]))
        story.append(sev_table)
        
        story.append(PageBreak())

        # ==================== EXECUTIVE SUMMARY ====================
        story.append(Paragraph("1. Executive Summary", self.style_h1))
        
        # Calculate totals first (needed for summary text)
        total_vulns = sum(vuln_counts.values())
        critical_high = vuln_counts['Critical'] + vuln_counts['High']
        
        # --- 1.1 Overview ---
        story.append(Paragraph("1.1 Overview", self.style_h2))
        
        overview_p1 = f"""<b>{self._rl(scan_data.target)}</b> engaged Scout Security to conduct automated security testing
        against their information environment to provide a practical demonstration of the security controls' 
        effectiveness as well as to provide an estimate of their susceptibility to exploitation and/or data breaches. 
        The test was performed in accordance with Scout Security's Automated Penetration Testing Method."""
        story.append(Paragraph(overview_p1, self.style_normal))
        story.append(Spacer(1, 8))
        
        if critical_high > 0:
            overview_p2 = f"""The target's information environment was found to contain <b>{total_vulns} security findings</b>, 
            including some notable security issues. <b>{vuln_counts['Critical']} Critical</b> and <b>{vuln_counts['High']} High</b> 
            severity vulnerabilities were identified which could potentially lead to data breaches or system compromise 
            if exploited by malicious actors."""
        else:
            overview_p2 = f"""The target's information environment was found to be reasonably secure with <b>{total_vulns} finding(s)</b> 
            documented. No critical or high-severity vulnerabilities were identified during this assessment, 
            indicating a strong baseline security posture."""
        story.append(Paragraph(overview_p2, self.style_normal))
        story.append(Spacer(1, 15))
        
        # --- 1.2 High-Level Test Outcomes ---
        story.append(Paragraph("1.2 High-Level Test Outcomes", self.style_h2))
        
        outcomes_intro = """The automated security assessment was designed to simulate reconnaissance and initial 
        exploitation attempts that a malicious actor might perform against the target infrastructure."""
        story.append(Paragraph(outcomes_intro, self.style_normal))
        story.append(Spacer(1, 8))
        
        # Determine risk narrative based on findings
        if vuln_counts['Critical'] > 0:
            outcome_text = f"""Overall, the target presents a <b>high-risk attack surface</b> with <b>{vuln_counts['Critical']} critical 
            vulnerabilities</b> that require immediate remediation. These issues could allow attackers to gain 
            unauthorized access, exfiltrate sensitive data, or compromise system integrity."""
        elif vuln_counts['High'] > 0:
            outcome_text = f"""Overall, the target presents a <b>moderate-to-high risk attack surface</b> with <b>{vuln_counts['High']} high 
            severity vulnerabilities</b> identified. These issues should be addressed promptly to reduce 
            the organization's exposure to potential attacks."""
        elif vuln_counts['Medium'] > 0:
            outcome_text = f"""Overall, the target presents a <b>moderate risk attack surface</b> with {vuln_counts['Medium']} 
            medium severity findings. While no immediately exploitable critical vulnerabilities were found, 
            the identified issues should be addressed as part of regular security maintenance."""
        else:
            outcome_text = """Overall, the target demonstrates a <b>strong security posture</b>. The automated assessment 
            did not identify any critical or high-severity vulnerabilities. Minor informational findings 
            should be reviewed but do not represent significant risk."""
        story.append(Paragraph(outcome_text, self.style_normal))
        story.append(Spacer(1, 8))
        
        # Tools summary
        tools_used = set()
        for v in all_vulns:
            if v.get('Tool'):
                tools_used.add(v.get('Tool'))
        if tools_used:
            tools_text = f"""The assessment utilized multiple security tools including: {', '.join(list(tools_used)[:5])}. 
            These tools provided comprehensive coverage of network, web application, and infrastructure security testing."""
            story.append(Paragraph(tools_text, self.style_normal))
        story.append(Spacer(1, 15))
        
        # --- 1.3 Overall Risk Rating ---
        story.append(Paragraph("1.3 Overall Risk Rating", self.style_h2))
        
        rating_intro = f"""Having considered the potential outcomes and the risk levels assessed for each 
        documented finding, Scout Security considers the overall risk exposure to be 
        <b>{risk_level.upper()}</b> (as determined using the Scout Risk Matrix below)."""
        story.append(Paragraph(rating_intro, self.style_normal))
        story.append(Spacer(1, 15))
        
        # Risk Matrix
        risk_matrix = self._create_risk_matrix(risk_score)
        matrix_table = Table([[risk_matrix]], hAlign='CENTER')
        story.append(matrix_table)
        story.append(Spacer(1, 8))
        story.append(Paragraph("<i>Fig. 1-1: Scout Risk Matrix</i>", 
                              ParagraphStyle('Caption', fontSize=9, alignment=TA_CENTER, textColor=self.COLORS['text_light'])))
        story.append(Spacer(1, 15))
        
        # --- 1.4 Prioritized Recommendations ---
        story.append(Paragraph("1.4 Prioritized Recommendations", self.style_h2))
        
        reco_intro = """Based on the results achieved during the security assessment, Scout Security makes the 
        following recommendations (presented by order of priority):"""
        story.append(Paragraph(reco_intro, self.style_normal))
        story.append(Spacer(1, 8))
        
        # Generate dynamic recommendations based on findings
        recommendations = []
        if vuln_counts['Critical'] > 0:
            recommendations.append("Address all Critical severity findings immediately - these represent active security risks.")
        if vuln_counts['High'] > 0:
            recommendations.append("Remediate High severity vulnerabilities within 7-14 days to reduce attack surface.")
        if vuln_counts['Medium'] > 0:
            recommendations.append("Schedule remediation of Medium severity findings as part of regular maintenance cycles.")
        
        # Add general recommendations
        recommendations.extend([
            "Implement a regular vulnerability scanning schedule (monthly recommended).",
            "Review and update security configurations based on industry best practices.",
            "Conduct security awareness training for staff members."
        ])
        
        # Limit to top 5 recommendations
        for i, reco in enumerate(recommendations[:5], 1):
            story.append(Paragraph(f"• {reco}", self.style_normal))
            story.append(Spacer(1, 4))
        
        story.append(Spacer(1, 15))
        
        # --- Key Metrics (visual summary) ---
        story.append(Paragraph("Key Metrics", self.style_h2))
        
        metrics_data = [
            [str(total_vulns), str(critical_high), duration_str, risk_level],
            ["Total Findings", "Critical/High", "Scan Duration", "Risk Level"]
        ]
        
        metrics_table = Table(metrics_data, colWidths=[95, 95, 95, 115], hAlign='CENTER')
        metrics_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (2,0), 24),
            ('FONTSIZE', (3,0), (3,0), 16),  # Smaller for Risk Level
            ('FONTSIZE', (0,1), (-1,1), 9),
            ('TEXTCOLOR', (0,0), (-1,0), self.COLORS['primary']),
            ('TEXTCOLOR', (1,0), (1,0), self.COLORS['critical'] if critical_high > 0 else self.COLORS['low']),
            ('TEXTCOLOR', (3,0), (3,0), risk_color),
            ('TEXTCOLOR', (0,1), (-1,1), self.COLORS['text_light']),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('BACKGROUND', (0,0), (-1,-1), self.COLORS['background']),
            ('BOX', (0,0), (-1,-1), 1, self.COLORS['background']),
        ]))
        story.append(metrics_table)
        
        story.append(PageBreak())

        # ==================== RISK OVERVIEW ====================
        story.append(Paragraph("2. Risk Overview", self.style_h1))
        
        # Pie chart - centered
        story.append(Paragraph("Vulnerability Distribution", self.style_h2))
        story.append(Spacer(1, 10))
        
        pie_chart = self._create_pie_chart(vuln_counts)
        pie_table = Table([[pie_chart]], hAlign='CENTER')
        story.append(pie_table)
        story.append(Spacer(1, 30))
        
        # Risk gauge - centered
        story.append(Paragraph("Overall Risk Score", self.style_h2))
        story.append(Spacer(1, 10))
        
        risk_gauge = self._create_risk_gauge(risk_score)
        gauge_table = Table([[risk_gauge]], hAlign='CENTER')
        story.append(gauge_table)
        
        story.append(PageBreak())

        # ==================== VULNERABILITY SUMMARY ====================
        story.append(Paragraph("3. Vulnerability Summary", self.style_h1))
        
        # Severity counts table
        counts_data = [
            [str(vuln_counts["Critical"]), str(vuln_counts["High"]), str(vuln_counts["Medium"]), str(vuln_counts["Low"]), str(vuln_counts["Info"])],
            ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        ]
        
        counts_table = Table(counts_data, colWidths=[90]*5, hAlign='CENTER')
        counts_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 24),
            ('FONTSIZE', (0,1), (-1,1), 8),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('TEXTCOLOR', (0,1), (-1,1), colors.white),
            ('BACKGROUND', (0,0), (0,-1), self.COLORS['critical']),
            ('BACKGROUND', (1,0), (1,-1), self.COLORS['high']),
            ('BACKGROUND', (2,0), (2,-1), self.COLORS['medium']),
            ('BACKGROUND', (3,0), (3,-1), self.COLORS['low']),
            ('BACKGROUND', (4,0), (4,-1), self.COLORS['info']),
            ('TOPPADDING', (0,0), (-1,-1), 12),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(counts_table)
        story.append(Spacer(1, 20))
        
        # Findings list
        if all_vulns:
            story.append(Paragraph("Findings Overview", self.style_h2))
            
            list_data = [["#", "Finding", "Severity", "Tool"]]
            for i, v in enumerate(all_vulns[:20], 1):  # Limit to first 20 in summary
                finding_name = v.get('Vulnerability', v.get('Name', 'Issue'))
                if len(finding_name) > 50:
                    finding_name = finding_name[:47] + "..."
                    
                list_data.append([
                    str(i),
                    Paragraph(self._rl(finding_name), self.style_small),
                    v['Severity'],
                    self._rl(v.get('Tool', 'N/A')[:15])
                ])
            
            list_table = Table(list_data, colWidths=[30, 280, 70, 100], hAlign='LEFT')
            list_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), self.COLORS['primary']),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 9),
                ('FONTSIZE', (0,1), (-1,-1), 9),
                ('GRID', (0,0), (-1,-1), 0.5, self.COLORS['background']),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('TOPPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, self.COLORS['background']]),
            ]))
            
            # Color severity column
            for r in range(1, len(list_data)):
                sev = list_data[r][2]
                bg = self.SEVERITY_COLORS.get(sev, self.COLORS['info'])
                list_table.setStyle(TableStyle([
                    ('BACKGROUND', (2,r), (2,r), bg),
                    ('TEXTCOLOR', (2,r), (2,r), colors.white),
                    ('ALIGN', (2,r), (2,r), 'CENTER'),
                ]))
            
            story.append(list_table)
        else:
            story.append(Paragraph("✅ No vulnerabilities were identified during this assessment.", self.style_normal))
        
        story.append(PageBreak())

        # ==================== DETAILED FINDINGS ====================
        story.append(Paragraph("4. Detailed Findings", self.style_h1))
        
        if not all_vulns:
            story.append(Paragraph("No detailed findings to report.", self.style_normal))
        else:
            for i, v in enumerate(all_vulns, 1):
                finding_elements = []
                
                # Finding header with severity badge on the right (same row)
                sev = v['Severity']
                sev_color = self.SEVERITY_COLORS.get(sev, self.COLORS['info'])
                
                header_text = f"<b>Finding {i}:</b> {self._rl(v.get('Vulnerability', v.get('Name', 'Issue')))}"
                
                # Create a table with header on left, badge on right
                header_badge_data = [[
                    Paragraph(header_text, self.style_h3),
                    Paragraph(f"<font color='white'><b>{sev.upper()}</b></font>", 
                             ParagraphStyle('Badge', fontSize=9, alignment=TA_CENTER, textColor=colors.white))
                ]]
                header_row = Table(header_badge_data, colWidths=[400, 80])
                header_row.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('ALIGN', (0,0), (0,0), 'LEFT'),
                    ('ALIGN', (1,0), (1,0), 'CENTER'),
                    ('BACKGROUND', (1,0), (1,0), sev_color),
                    ('TOPPADDING', (1,0), (1,0), 6),
                    ('BOTTOMPADDING', (1,0), (1,0), 6),
                    ('LEFTPADDING', (1,0), (1,0), 8),
                    ('RIGHTPADDING', (1,0), (1,0), 8),
                ]))
                finding_elements.append(header_row)
                finding_elements.append(Spacer(1, 8))
                
                # Details table
                desc = v.get("Description", "No description available.")
                tool = v.get("Tool", "Unknown")
                remediation = v.get("Remediation", v.get("Mitigation", "No remediation provided."))
                
                # References
                refs = []
                if v.get("OWASP"): refs.append(f"OWASP: {v['OWASP']}")
                if v.get("CWE"): refs.append(f"CWE: {v['CWE']}")
                refs_text = " | ".join(refs) if refs else "N/A"
                
                details_data = [
                    [Paragraph("<b>Description</b>", self.style_small), Paragraph(self._rl(desc), self.style_normal)],
                    [Paragraph("<b>Tool</b>", self.style_small), Paragraph(self._rl(tool), self.style_normal)],
                    [Paragraph("<b>References</b>", self.style_small), Paragraph(self._rl(refs_text), self.style_small)],
                    [Paragraph("<b>Remediation</b>", self.style_small), Paragraph(self._rl(remediation), self.style_normal)],
                ]
                
                # Add evidence if available
                evidence = v.get("Evidence", "")
                if evidence and len(evidence) < 500:
                    evidence_escaped = html.escape(str(evidence))[:500]
                    details_data.append([
                        Paragraph("<b>Evidence</b>", self.style_small),
                        Paragraph(f"<font name='Courier' size='7'>{evidence_escaped}</font>", self.style_normal)
                    ])
                
                details_table = Table(details_data, colWidths=[80, 400], hAlign='LEFT')
                details_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (0,-1), self.COLORS['background']),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('BOX', (0,0), (-1,-1), 0.5, self.COLORS['background']),
                ]))
                finding_elements.append(details_table)
                finding_elements.append(Spacer(1, 15))
                
                # Try to keep finding together
                story.append(KeepTogether(finding_elements))

        # Build with footer
        target = scan_data.target
        doc.build(story, onFirstPage=lambda c, d: self._add_footer(c, d, target),
                  onLaterPages=lambda c, d: self._add_footer(c, d, target))
        
        return output_path
