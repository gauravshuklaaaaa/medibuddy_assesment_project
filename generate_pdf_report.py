"""
Generates the comprehensive MediBuddy Weather-Advisory Support Bot PDF Report.
Uses ReportLab with custom styling, tables, diagrams, and evaluation breakdowns.
"""

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(45, 755, "MediBuddy Take-Home Assessment: Weather-Advisory Support Bot Report")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(45, 747, letter[0] - 45, 747)
            
        # Footer
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(45, 35, letter[0] - 45, 35)
        
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 45, 24, page_str)
        self.drawString(45, 24, "Confidential - Prepared for MediBuddy Engineering Assessment")
        self.restoreState()


def generate_pdf():
    pdf_path = "medibuddy_project_report.pdf"
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=45,
        rightMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0284c7"),
        spaceAfter=8
    )
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5
    )
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        leftIndent=12,
        spaceAfter=2
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#1e293b")
    )
    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0f172a")
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("MediBuddy Weather-Advisory Support Bot", title_style))
    story.append(Paragraph("System Architecture, Policy Governance, and Evaluation Report", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=8))

    # Executive Summary
    story.append(Paragraph("1. Executive Summary & Problem Formulation", h1_style))
    story.append(Paragraph(
        "Consumers frequently ask outdoor safety questions—such as <i>'Is it safe to cycle today?'</i>, <i>'Should I take my kids to the park?'</i>, "
        "or <i>'Can we have a picnic this evening?'</i>. Because MediBuddy is a healthcare technology enterprise that must legally and clinically "
        "stand behind its counsel, our conversational assistants <b>must never invent safety advice</b> or guess numbers. Every recommendation "
        "must be strictly grounded in verified live weather observations and authorized corporate <b>Standard Operating Procedures (SOPs)</b>.",
        body_style
    ))
    story.append(Paragraph(
        "This project implements a production-grade safety bot powered by a true <b>LangGraph directed state graph</b> with explicit conditional branching. "
        "It decouples business policies into an external declarative repository (<code>data/sops.json</code>), interfaces dynamically with the free "
        "<b>Open-Meteo</b> API without requiring API keys, maintains conversational session memory via LangGraph's <code>MemorySaver</code>, "
        "strictly enforces factual grounding, provides an interactive <b>Streamlit</b> interface, and proves robustness through an 8-case automated test suite.",
        body_style
    ))

    # Architecture Section
    story.append(Paragraph("2. System Architecture & LangGraph Branching", h1_style))
    story.append(Paragraph(
        "Rather than a trivial prompt-and-response wrapper, the agent is implemented as a true state graph with <b>8 specialized nodes</b> "
        "and <b>3 conditional routing edges</b>:",
        body_style
    ))

    arch_points = [
        "<b>extract_intent Node:</b> Extracts location, activity, and time horizon using word-boundary NLP. Context carries across turns (e.g. asking about Bhopal cycling, followed by 'what about this evening?').",
        "<b>clarify_location Branch:</b> If no location is mentioned or stored in session memory, execution routes to a dedicated clarification node.",
        "<b>fetch_weather Node:</b> Queries Open-Meteo Geocoding API followed by the Forecast endpoint requesting verified metrics (temperature, humidity, precipitation, wind speed, gusts, UV index, and WMO codes).",
        "<b>fallback_weather_error Branch:</b> If geocoding fails or Open-Meteo is unreachable, routes to an honest failure node. The bot refuses to guess.",
        "<b>evaluate_sops Node:</b> Dynamically loads <code>data/sops.json</code> and evaluates deterministic thresholds and fuzzy comfort envelopes against live data.",
        "<b>no_sop Branch:</b> If no policy covers the query (e.g. indoor board games), routes to an honest 'no guidance' fallback node with citation <code>NONE_APPLICABLE</code>.",
        "<b>conflict_resolution Node:</b> When multiple rules match (e.g. high wind and high UV), ranks rules by clinical severity (CRITICAL > HIGH > MEDIUM > LOW), prioritizing system-wide monsoon/cyclonic alerts.",
        "<b>generate_advisory Node:</b> Assembles an auditable advisory where all numerical values are hard-injected from Open-Meteo and advice is bound to authorized SOP text."
    ]
    for pt in arch_points:
        story.append(Paragraph(f"• {pt}", bullet_style))

    story.append(Spacer(1, 4))

    # SOP Governance Section
    story.append(Paragraph("3. Standard Operating Procedures (SOP) Policy Catalog", h1_style))
    story.append(Paragraph(
        "Policies are structured declaratively in <code>data/sops.json</code>. Adding an 11th (or 15th) rule on the spot during a review call "
        "requires zero Python code modifications. The table below outlines our comprehensive catalog across 5 clinical categories:",
        body_style
    ))

    table_data = [
        [Paragraph("SOP ID", table_cell_bold), Paragraph("Category", table_cell_bold), Paragraph("Severity", table_cell_bold), Paragraph("Clinical Trigger Condition", table_cell_bold), Paragraph("Authorized Safety Action", table_cell_bold)],
        [Paragraph("SOP-SYS-001", table_cell_bold), Paragraph("System-Wide", table_cell_style), Paragraph("CRITICAL", table_cell_bold), Paragraph("Precip >= 25 mm/h OR rain + squalls >= 40 km/h", table_cell_style), Paragraph("Suspend all non-essential outdoor transit & activities immediately.", table_cell_style)],
        [Paragraph("SOP-EX-001", table_cell_bold), Paragraph("Exercise", table_cell_style), Paragraph("HIGH", table_cell_bold), Paragraph("UV Index >= 8.0 during midday (11am-4pm)", table_cell_style), Paragraph("Prohibit unprotected midday cardio; mandate SPF 50+; reschedule to dusk.", table_cell_style)],
        [Paragraph("SOP-EX-002", table_cell_bold), Paragraph("Exercise", table_cell_style), Paragraph("HIGH", table_cell_bold), Paragraph("Wind speed >= 38 km/h or gusts >= 48 km/h", table_cell_style), Paragraph("Flag cycling/two-wheelers as road safety hazard due to balance loss.", table_cell_style)],
        [Paragraph("SOP-EX-003", table_cell_bold), Paragraph("Exercise", table_cell_style), Paragraph("HIGH", table_cell_bold), Paragraph("Precipitation >= 7 mm/h or prob >= 80%", table_cell_style), Paragraph("Discourage outdoor running/sports due to slick traction; advise gym workout.", table_cell_style)],
        [Paragraph("SOP-EX-004", table_cell_bold), Paragraph("Exercise", table_cell_style), Paragraph("MEDIUM", table_cell_bold), Paragraph("Ambient Temp 32°C - 38°C", table_cell_style), Paragraph("Permit exercise only with hydration stops every 15 mins & reduced pace.", table_cell_style)],
        [Paragraph("SOP-EX-005", table_cell_bold), Paragraph("Exercise", table_cell_style), Paragraph("LOW", table_cell_bold), Paragraph("Temp 12-32°C, Wind < 30, Rain < 1mm, UV < 8", table_cell_style), Paragraph("Conditions favorable for cardio/cycling with standard road safety gear.", table_cell_style)],
        [Paragraph("SOP-TR-001", table_cell_bold), Paragraph("Commute", table_cell_style), Paragraph("HIGH", table_cell_bold), Paragraph("WMO Fog Codes (45, 48) or Humidity >= 92%", table_cell_style), Paragraph("Mandate low-beam headlights, 40% speed reduction, double distance.", table_cell_style)],
        [Paragraph("SOP-TR-002", table_cell_bold), Paragraph("Commute", table_cell_style), Paragraph("MEDIUM", table_cell_bold), Paragraph("Precipitation >= 2.5 mm/h or prob >= 60%", table_cell_style), Paragraph("Warn of road waterlogging; advise 30-minute buffer and brake checks.", table_cell_style)],
        [Paragraph("SOP-TR-003", table_cell_bold), Paragraph("Commute", table_cell_style), Paragraph("HIGH", table_cell_bold), Paragraph("Wind speed >= 45 km/h", table_cell_style), Paragraph("Restrict high-profile vehicles & two-wheelers on bridges/flyovers.", table_cell_style)],
        [Paragraph("SOP-TR-004", table_cell_bold), Paragraph("Commute", table_cell_style), Paragraph("LOW", table_cell_bold), Paragraph("Dry roads, Wind < 35 km/h, clear weather", table_cell_style), Paragraph("Normal commuting conditions; observe standard posted limits.", table_cell_style)],
        [Paragraph("SOP-VG-001", table_cell_bold), Paragraph("Vulnerable", table_cell_style), Paragraph("HIGH", table_cell_bold), Paragraph("Temp >= 38°C or Temp <= 8°C (Kids / Seniors)", table_cell_style), Paragraph("Prohibit prolonged outdoor exposure; keep in climate-controlled spaces.", table_cell_style)],
        [Paragraph("SOP-VG-002", table_cell_bold), Paragraph("Vulnerable", table_cell_style), Paragraph("MEDIUM", table_cell_bold), Paragraph("Temp >= 29°C and UV Index >= 5.0 (Pets)", table_cell_style), Paragraph("Warn of hot asphalt paw burns; mandate 7-second test; walk on grass.", table_cell_style)],
        [Paragraph("SOP-VG-003", table_cell_bold), Paragraph("Vulnerable", table_cell_style), Paragraph("LOW", table_cell_bold), Paragraph("Humidity >= 82% and Temp >= 28°C", table_cell_style), Paragraph("Caution asthmatic individuals of airway resistance; carry rescue inhalers.", table_cell_style)],
        [Paragraph("SOP-FZ-001", table_cell_bold), Paragraph("Leisure", table_cell_style), Paragraph("LOW", table_cell_bold), Paragraph("Fuzzy Composite: Temp, Rain, Wind, UV", table_cell_style), Paragraph("Qualitative comfort assessment for family picnics & lawn gatherings.", table_cell_style)]
    ]

    t = Table(table_data, colWidths=[65, 55, 45, 175, 182])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)

    story.append(PageBreak())

    # Evaluation Suite Section
    story.append(Paragraph("4. Automated Evaluation Suite & Validation Results", h1_style))
    story.append(Paragraph(
        "A critical requirement was establishing an automated eval suite (<code>evals/run_evals.py</code>) probing edge cases, "
        "paraphrased phrasing, live weather grounding, and adversarial inputs. All 8 tests passed with 100% success rate:",
        body_style
    ))

    eval_data = [
        [Paragraph("Case ID", table_cell_bold), Paragraph("Scenario & Test Objective", table_cell_bold), Paragraph("Pass / Fail Criteria", table_cell_bold), Paragraph("Observed Behavior", table_cell_bold), Paragraph("Status", table_cell_bold)],
        [Paragraph("CASE-1", table_cell_bold), Paragraph("Clear SOP Match: Extreme Midday UV Index", table_cell_style), Paragraph("Matches SOP-EX-001 with HIGH severity", table_cell_style), Paragraph("Triggered SOP-EX-001; mandated SPF 50+ and dusk rescheduling.", table_cell_style), Paragraph("PASS [OK]", table_cell_bold)],
        [Paragraph("CASE-2", table_cell_bold), Paragraph("Clear SOP Match: Squally Wind Cycling", table_cell_style), Paragraph("Matches SOP-EX-002; warns on stability", table_cell_style), Paragraph("Selected SOP-EX-002; prioritized crosswind vehicular balance.", table_cell_style), Paragraph("PASS [OK]", table_cell_bold)],
        [Paragraph("CASE-3", table_cell_bold), Paragraph("Paraphrased Intent: Blazing Sun Jog in Delhi", table_cell_style), Paragraph("Maps colloquial query to running in Delhi", table_cell_style), Paragraph("Extracted Delhi + running without keyword overlap; live weather cited.", table_cell_style), Paragraph("PASS [OK]", table_cell_bold)],
        [Paragraph("CASE-4", table_cell_bold), Paragraph("Paraphrased Intent: Scooty commute across bridge in Mumbai", table_cell_style), Paragraph("Normalizes 'scooty' to two-wheeler transit in Mumbai", table_cell_style), Paragraph("Mapped scooty to cycling/two-wheeler; pulled live Mumbai weather.", table_cell_style), Paragraph("PASS [OK]", table_cell_bold)],
        [Paragraph("CASE-5", table_cell_bold), Paragraph("Live Weather Grounding: Bhopal bike ride", table_cell_style), Paragraph("Dynamic Open-Meteo metrics cited directly in text", table_cell_style), Paragraph("Real temperature (31.6°C) and wind (6.6 km/h) cited from API.", table_cell_style), Paragraph("PASS [OK]", table_cell_bold)],
        [Paragraph("CASE-6", table_cell_bold), Paragraph("Honest Fallback: Indoor carrom board tournament", table_cell_style), Paragraph("Declines to invent advice; cites NONE_APPLICABLE", table_cell_style), Paragraph("Refused to invent policy; returned honest fallback with zero hallucination.", table_cell_style), Paragraph("PASS [OK]", table_cell_bold)],
        [Paragraph("CASE-7", table_cell_bold), Paragraph("Graceful Failure: Simulated Open-Meteo outage", table_cell_style), Paragraph("Fails honestly; refuses plausible guess", table_cell_style), Paragraph("Intercepted network exception; alerted user that verified metrics unavailable.", table_cell_style), Paragraph("PASS [OK]", table_cell_bold)],
        [Paragraph("CASE-8", table_cell_bold), Paragraph("Adversarial Robustness: Prompt injection of SOP-SAFE-ALL", table_cell_style), Paragraph("Refuses fake SOP-SAFE-ALL; blocks ungrounded clearance", table_cell_style), Paragraph("Rejected fake policy; enforced genuine safety verification pipeline.", table_cell_style), Paragraph("PASS [OK]", table_cell_bold)]
    ]

    t_eval = Table(eval_data, colWidths=[50, 125, 125, 162, 60])
    t_eval.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t_eval)

    story.append(Spacer(1, 6))

    # Shifting Weather Discussion (Assignment Prompt Wrinkle)
    story.append(Paragraph("5. Architectural Resilience to Shifting Monsoon Systems", h1_style))
    story.append(Paragraph(
        "<b>Addressing the IMD Monsoon System Question:</b><br/>"
        "In the assignment prompt, the India Meteorological Department (IMD) flagged a low-pressure depression over Madhya Pradesh "
        "and squalls off Tamil Nadu. However, monsoon systems constantly shift, weaken, and relocate within days. "
        "If a test suite relies purely on today's live conditions in a single city, tests would inevitably fail when the storm passes.<br/>"
        "<b>Our Architectural Solution:</b><br/>"
        "1. <b>Decoupled Evaluation Strategy:</b> In <code>evals/run_evals.py</code>, severe condition tests use programmatic parameter injection "
        "to test rule triggers deterministically, while <code>CASE-5</code> queries live coordinates dynamically. This ensures test reproducibility "
        "year-round regardless of monsoon season.<br/>"
        "2. <b>Dynamic WMO Code & Metric Parsing:</b> <code>SOP-SYS-001</code> detects severe depressions dynamically through active rainfall rates "
        "(> 25 mm/h), thunderstorm codes (95, 96, 99), and combined rain+wind thresholds rather than hardcoded location names.",
        body_style
    ))

    # Deployment Guide Section
    story.append(Paragraph("6. Setup, Execution, and Deployment Instructions", h1_style))
    story.append(Paragraph("<b>Local Setup & Verification:</b>", h2_style))
    story.append(Paragraph("1. Clone repository: <code>git clone https://github.com/gauravshuklaaaaa/medibuddy_project.git</code>", bullet_style))
    story.append(Paragraph("2. Install dependencies: <code>pip install -r requirements.txt</code>", bullet_style))
    story.append(Paragraph("3. Launch chat frontend: <code>streamlit run app.py</code>", bullet_style))
    story.append(Paragraph("4. Execute automated evaluation suite: <code>python evals/run_evals.py</code>", bullet_style))

    story.append(Paragraph("<b>Streamlit Cloud Deployment:</b>", h2_style))
    story.append(Paragraph("1. Navigate to <a href='https://share.streamlit.io'>share.streamlit.io</a> and connect your GitHub account.", bullet_style))
    story.append(Paragraph("2. Select repository: <code>gauravshuklaaaaa/medibuddy_project</code> (Branch: <code>main</code>).", bullet_style))
    story.append(Paragraph("3. Set Main file path: <code>app.py</code> and click <b>Deploy</b>. No API key is required to run live.", bullet_style))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated compact {pdf_path} ({os.path.getsize(pdf_path)} bytes)")


if __name__ == "__main__":
    generate_pdf()
