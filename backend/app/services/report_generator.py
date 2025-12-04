from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime
import json
import html
import os

class ReportGenerator:
    def generate_report(self, scan_data, scan_results, output_path):
        doc = SimpleDocTemplate(output_path, pagesize=letter,
                                rightMargin=50, leftMargin=50,
                                topMargin=50, bottomMargin=50)
        styles = getSampleStyleSheet()
        story = []

        # --- Colors & Styles ---
        # TCM-like Colors
        col_critical = colors.HexColor('#C00000') # Red
        col_high = colors.HexColor('#FF0000')     # Bright Red (or Orange-Red) - actually TCM uses Red for Critical, Orange for High? 
        # Let's stick to standard: Critical=Red, High=Orange, Medium=Yellow, Low=Green, Info=Blue
        # But TCM image shows: Critical (Red), High (Red?), Moderate (Yellow), Low (Green), Info (Blue)
        # Wait, the image "uploaded_image_2" shows:
        # Critical (Red 9.0-10.0), High (Red 7.0-8.9), Moderate (Yellow 4.0-6.9), Low (Green 0.1-3.9), Info (Blue N/A)
        # Actually High looks Red too in the image? Let's use a slightly lighter red or orange for High to distinguish.
        # "uploaded_image_0_...246828.png" (Summary) shows:
        # Critical (Red), High (Red), Moderate (Yellow), Low (Green), Informational (Blue).
        # I will use:
        col_critical = colors.HexColor('#D00000') 
        col_high = colors.HexColor('#FF0000')
        col_mod = colors.HexColor('#FFC000')
        col_low = colors.HexColor('#00B050')
        col_info = colors.HexColor('#0070C0')
        
        col_header_bg = colors.HexColor('#1F4E79') # Dark Blue for headers
        col_text = colors.HexColor('#262626')
        
        # Styles
        style_title = ParagraphStyle('Title', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=24, textColor=colors.black, alignment=TA_CENTER, spaceAfter=20)
        style_subtitle = ParagraphStyle('Subtitle', parent=styles['Normal'], fontName='Helvetica', fontSize=16, textColor=colors.black, alignment=TA_CENTER)
        style_h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, textColor=col_header_bg, spaceBefore=20, spaceAfter=10, borderPadding=5, borderWidth=0, borderColor=col_header_bg, backColor=None)
        # Add a line under H1
        
        style_h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=14, textColor=colors.black, spaceBefore=15, spaceAfter=8)
        style_normal = ParagraphStyle('Normal', parent=styles['Normal'], fontName='Helvetica', fontSize=10, textColor=col_text, leading=14, alignment=TA_LEFT)
        style_footer = ParagraphStyle('Footer', parent=styles['Normal'], fontName='Helvetica', fontSize=8, textColor=colors.gray, alignment=TA_CENTER)
        style_code = ParagraphStyle('Code', parent=styles['Code'], fontName='Courier', fontSize=8, backColor=colors.whitesmoke, borderPadding=5)

        # --- Helper: Footer ---
        def add_footer(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.black)
            
            # Bottom Line
            canvas.line(50, 50, letter[0]-50, 50)
            
            # Text
            footer_text = f"{scan_data.target}"
            canvas.drawCentredString(letter[0]/2, 40, "BUSINESS CONFIDENTIAL")
            canvas.drawCentredString(letter[0]/2, 30, f"Copyright © Sarral Security")
            
            canvas.drawString(50, 30, footer_text)
            canvas.drawRightString(letter[0]-50, 30, f"Page {doc.page}")
            
            canvas.restoreState()

        # --- Process Data ---
        all_vulns = []
        vuln_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
        
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
                            if sev == "Moderate": sev = "Medium"
                            if sev not in vuln_counts: sev = "Info"
                            v['Severity'] = sev
                            all_vulns.append(v)
                            vuln_counts[sev] += 1
                except:
                    pass
        
        # Sort: Critical -> Info
        sev_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
        all_vulns.sort(key=lambda x: sev_order.get(x['Severity'], 5))

        # --- 1. Cover Page ---
        story.append(Spacer(1, 2*inch))
        # Logo could go here
        story.append(Paragraph("SARRAL SECURITY", style_title)) 
        story.append(Spacer(1, 1.5*inch))
        
        story.append(Paragraph(f"{scan_data.target}", style_title))
        story.append(Paragraph("Security Assessment Findings Report", style_subtitle))
        
        story.append(Spacer(1, 2*inch))
        story.append(Paragraph("Business Confidential", style_subtitle))
        
        story.append(Spacer(1, 1.5*inch))
        story.append(Paragraph(f"Date: {datetime.now().strftime('%B %d, %Y')}", style_normal))
        story.append(Paragraph(f"Project: SAR-{scan_data.id:03d}", style_normal))
        story.append(Paragraph("Version 1.0", style_normal))
        
        story.append(PageBreak())

        # --- 2. Confidentiality & Disclaimer ---
        story.append(Paragraph("Confidentiality Statement", style_h1))
        story.append(Paragraph("This document is the exclusive property of the Client and Sarral Security. This document contains proprietary and confidential information. Duplication, redistribution, or use, in whole or in part, in any form, requires consent.", style_normal))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("Disclaimer", style_h1))
        story.append(Paragraph("A penetration test is considered a snapshot in time. The findings and recommendations reflect the information gathered during the assessment and not any changes or modifications made outside of that period.", style_normal))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("Contact Information", style_h1))
        contact_data = [
            ["Name", "Title", "Contact Information"],
            ["Sarral Scan", "Automated Scanner", "support@sarral.io"],
            ["Client", "Security Team", f"security@{scan_data.target}"]
        ]
        t_contact = Table(contact_data, colWidths=[150, 150, 200], hAlign='LEFT')
        t_contact.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), col_header_bg),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#DCE6F1'))
        ]))
        story.append(t_contact)
        story.append(PageBreak())

        # --- 3. Severity Ratings ---
        story.append(Paragraph("Finding Severity Ratings", style_h1))
        story.append(Paragraph("The following table defines levels of severity and corresponding CVSS score range used throughout the document.", style_normal))
        story.append(Spacer(1, 10))
        
        sev_definitions = [
            ["Critical", "9.0-10.0", "Exploitation is straightforward and usually results in system-level compromise."],
            ["High", "7.0-8.9", "Exploitation is more difficult but could cause elevated privileges and data loss."],
            ["Moderate", "4.0-6.9", "Vulnerabilities exist but are not exploitable or require extra steps."],
            ["Low", "0.1-3.9", "Vulnerabilities are non-exploitable but reduce attack surface."],
            ["Informational", "N/A", "No vulnerability exists. Additional information provided."]
        ]
        
        sev_data = [["Severity", "CVSS V3 Range", "Definition"]]
        for row in sev_definitions:
            sev_data.append([
                row[0], 
                row[1], 
                Paragraph(row[2], style_normal) # Wrap definition in Paragraph
            ])

        t_sev = Table(sev_data, colWidths=[80, 80, 350], hAlign='LEFT')
        t_sev.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), col_header_bg),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            # Row Colors
            ('BACKGROUND', (0,1), (0,1), col_critical),
            ('BACKGROUND', (0,2), (0,2), col_high),
            ('BACKGROUND', (0,3), (0,3), col_mod),
            ('BACKGROUND', (0,4), (0,4), col_low),
            ('BACKGROUND', (0,5), (0,5), col_info),
            ('TEXTCOLOR', (0,1), (0,5), colors.white),
            ('ALIGN', (0,0), (1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_sev)
        story.append(PageBreak())

        # --- 4. Executive Summary ---
        story.append(Paragraph("Executive Summary", style_h1))
        story.append(Paragraph(f"Sarral Security evaluated {scan_data.target}'s security posture on {datetime.now().strftime('%B %d, %Y')}. The following sections provide a high-level overview of vulnerabilities discovered.", style_normal))
        story.append(Spacer(1, 10))
        
        story.append(Paragraph("Testing Summary", style_h2))
        story.append(Paragraph("The assessment evaluated the target's external network security posture. The team performed vulnerability scanning and reconnaissance to identify potential risks such as exposed services, misconfigurations, and sensitive information disclosure.", style_normal))
        story.append(PageBreak())

        # --- 5. Vulnerability Summary & Report Card ---
        story.append(Paragraph("Vulnerability Summary & Report Card", style_h1))
        
        # Counts Table
        counts_data = [
            [str(vuln_counts["Critical"]), str(vuln_counts["High"]), str(vuln_counts["Medium"]), str(vuln_counts["Low"]), str(vuln_counts["Info"])],
            ["Critical", "High", "Moderate", "Low", "Informational"]
        ]
        t_counts = Table(counts_data, colWidths=[100]*5)
        t_counts.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 18),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('BACKGROUND', (0,0), (0,0), col_critical),
            ('BACKGROUND', (1,0), (1,0), col_high),
            ('BACKGROUND', (2,0), (2,0), col_mod),
            ('BACKGROUND', (3,0), (3,0), col_low),
            ('BACKGROUND', (4,0), (4,0), col_info),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(t_counts)
        story.append(Spacer(1, 20))

        # Findings List Table
        list_data = [["Finding", "Severity", "Recommendation"]]
        for i, v in enumerate(all_vulns, 1):
            rec = v.get("Remediation", v.get("Mitigation", "See details."))
            # Truncate rec for summary if too long, but let Paragraph handle wrapping
            if len(rec) > 200: rec = rec[:200] + "..."
            
            # Color for severity cell
            s = v['Severity']
            
            list_data.append([
                Paragraph(f"SAR-{i:03d}: {v.get('Vulnerability', v.get('Name', 'Issue'))}", style_normal),
                s,
                Paragraph(rec, style_normal)
            ])
        
        if len(list_data) > 1:
            t_list = Table(list_data, colWidths=[200, 70, 240], hAlign='LEFT')
            t_list.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), col_header_bg),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('VALIGN', (0,0), (-1,-1), 'TOP'), # Align top for wrapped text
            ]))
            # Apply row colors for severity
            for r in range(1, len(list_data)):
                # Note: list_data[r][1] is just the string "Critical", etc.
                s = list_data[r][1]
                bg = colors.white
                if s == 'Critical': bg = col_critical
                elif s == 'High': bg = col_high
                elif s == 'Medium': bg = col_mod
                elif s == 'Low': bg = col_low
                elif s == 'Info': bg = col_info
                t_list.setStyle(TableStyle([('BACKGROUND', (1,r), (1,r), bg), ('TEXTCOLOR', (1,r), (1,r), colors.white if s != 'Medium' else colors.black)]))
            
            story.append(t_list)
        else:
            story.append(Paragraph("No findings to report.", style_normal))
            
        story.append(PageBreak())

        # --- 6. Technical Findings ---
        story.append(Paragraph("Technical Findings", style_h1))
        
        for i, v in enumerate(all_vulns, 1):
            title = f"Finding SAR-{i:03d}: {v.get('Vulnerability', v.get('Name', 'Issue'))} ({v['Severity']})"
            story.append(Paragraph(title, style_h2))
            
            # Detailed Table
            # Row 1: Description
            # Row 2: Risk (Likelihood / Impact)
            # Row 3: System
            # Row 4: Tools Used
            # Row 5: References
            
            desc = v.get("Description", "No description.")
            
            # Dynamic Risk Assessment
            likelihood = v.get("Likelihood", "Medium") # Default to Medium if missing
            impact = v.get("Impact", v['Severity'])    # Default to Severity if missing
            risk_text = f"Likelihood: {likelihood}\nImpact: {impact}"
            
            system = scan_data.target
            tool = v.get("Tool", "Unknown")
            # OWASP & CWE
            owasp = v.get("OWASP", "")
            cwe = v.get("CWE", "")
            refs_text = ""
            if owasp: refs_text += f"OWASP: {owasp}\n"
            if cwe: refs_text += f"CWE: {cwe}"
            if not refs_text: refs_text = "N/A"

            det_data = [
                [Paragraph("<b>Description:</b>", style_normal), Paragraph(desc, style_normal)],
                [Paragraph("<b>Risk:</b>", style_normal), Paragraph(risk_text, style_normal)],
                [Paragraph("<b>System:</b>", style_normal), Paragraph(system, style_normal)],
                [Paragraph("<b>Tools Used:</b>", style_normal), Paragraph(tool, style_normal)],
                [Paragraph("<b>References:</b>", style_normal), Paragraph(refs_text, style_normal)]
            ]
            
            # Evidence
            evidence = v.get("Evidence", "")
            if evidence:
                det_data.append([
                    Paragraph("<b>Evidence:</b>", style_normal), 
                    Paragraph(f"<font name='Courier' size='8'>{html.escape(evidence)}</font>", style_normal)
                ])
            
            t_det = Table(det_data, colWidths=[100, 400], hAlign='LEFT')
            t_det.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#DCE6F1')), # Light blue for labels
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 5),
                ('RIGHTPADDING', (0,0), (-1,-1), 5),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(t_det)
            story.append(Spacer(1, 10))
            
            # Evidence
            # story.append(Paragraph("Evidence", style_h2))
            # story.append(Paragraph("Raw output:", style_normal))
            # raw_out = html.escape(v.get("raw_output", "")[:500]).replace('\n', '<br/>')
            # story.append(Paragraph(raw_out, style_code))
            
            # Remediation
            story.append(Paragraph("Remediation", style_h2))
            rem = v.get("Remediation", v.get("Mitigation", "No remediation provided."))
            story.append(Paragraph(rem, style_normal))
            
            story.append(Spacer(1, 20))
            # Divider
            story.append(Table([[""]], colWidths=[500], style=[('LINEBELOW', (0,0), (-1,-1), 1, colors.black)]))
            story.append(Spacer(1, 20))
            
            # 1 finding per page
            story.append(PageBreak())

        # Build
        doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
        return output_path
