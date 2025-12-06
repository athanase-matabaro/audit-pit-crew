"""
PDF Report Generator for Pre-Audit Clearance Certificates.

Generates professional PDF reports showing security scan results,
designed for founders to share with investors and auditors.

Uses reportlab for PDF generation - a pure Python solution with no
external dependencies like wkhtmltopdf.
"""

import io
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Rect, String, Circle
from reportlab.graphics.charts.piecharts import Pie

logger = logging.getLogger(__name__)


@dataclass
class IssuesSummary:
    """Summary of issues by severity."""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    informational: int = 0
    
    @property
    def total(self) -> int:
        return self.critical + self.high + self.medium + self.low + self.informational
    
    @property
    def blocking(self) -> int:
        """Issues that would block a PR (Critical + High)."""
        return self.critical + self.high
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "Critical": self.critical,
            "High": self.high,
            "Medium": self.medium,
            "Low": self.low,
            "Informational": self.informational,
        }


@dataclass
class ReportData:
    """Data structure for PDF report generation."""
    repo_owner: str
    repo_name: str
    scan_date: datetime
    commit_sha: str
    branch: str = "main"
    tools_used: List[str] = field(default_factory=list)
    issues_summary: IssuesSummary = field(default_factory=IssuesSummary)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    scan_duration_seconds: float = 0.0
    files_scanned: int = 0
    solidity_version: str = "0.8.x"
    
    @property
    def is_clearance_passed(self) -> bool:
        """Check if the scan passes clearance (no Critical or High issues)."""
        return self.issues_summary.blocking == 0
    
    @property
    def repo_full_name(self) -> str:
        return f"{self.repo_owner}/{self.repo_name}"


class PreAuditReportGenerator:
    """
    Generates professional Pre-Audit Clearance Certificate PDFs.
    
    The certificate includes:
    - Repository and scan metadata
    - Pass/Fail status badge
    - Issues breakdown by severity
    - Tool coverage summary
    - Individual issue details
    - Recommendations section
    """
    
    # Color scheme
    COLORS = {
        "primary": colors.HexColor("#1a73e8"),      # Blue
        "success": colors.HexColor("#34a853"),      # Green
        "warning": colors.HexColor("#fbbc04"),      # Yellow
        "danger": colors.HexColor("#ea4335"),       # Red
        "dark": colors.HexColor("#202124"),         # Dark gray
        "light": colors.HexColor("#f8f9fa"),        # Light gray
        "muted": colors.HexColor("#5f6368"),        # Muted text
        "critical": colors.HexColor("#9c27b0"),     # Purple
        "high": colors.HexColor("#ea4335"),         # Red
        "medium": colors.HexColor("#ff9800"),       # Orange
        "low": colors.HexColor("#ffc107"),          # Yellow
        "info": colors.HexColor("#2196f3"),         # Light blue
    }
    
    def __init__(self, page_size=letter):
        """Initialize the report generator."""
        self.page_size = page_size
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=self.COLORS["dark"],
            alignment=TA_CENTER,
            spaceAfter=20,
        ))
        
        # Subtitle style
        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            parent=self.styles['Normal'],
            fontSize=14,
            textColor=self.COLORS["muted"],
            alignment=TA_CENTER,
            spaceAfter=30,
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=self.COLORS["primary"],
            spaceBefore=20,
            spaceAfter=10,
            borderPadding=5,
        ))
        
        # Badge text style
        self.styles.add(ParagraphStyle(
            name='BadgeText',
            parent=self.styles['Normal'],
            fontSize=18,
            textColor=colors.white,
            alignment=TA_CENTER,
        ))
        
        # Issue title style
        self.styles.add(ParagraphStyle(
            name='IssueTitle',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=self.COLORS["dark"],
            fontName='Helvetica-Bold',
            spaceBefore=8,
            spaceAfter=4,
        ))
        
        # Issue body style
        self.styles.add(ParagraphStyle(
            name='IssueBody',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=self.COLORS["muted"],
            leftIndent=10,
        ))
        
        # Footer style
        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=self.COLORS["muted"],
            alignment=TA_CENTER,
        ))
    
    def generate(self, data: ReportData) -> bytes:
        """
        Generate a PDF report from the scan data.
        
        Args:
            data: ReportData containing scan results
            
        Returns:
            PDF content as bytes
        """
        buffer = io.BytesIO()
        
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )
        
        # Build the document content
        story = []
        
        # Header
        story.extend(self._build_header(data))
        
        # Status badge
        story.extend(self._build_status_badge(data))
        
        # Summary section
        story.extend(self._build_summary_section(data))
        
        # Issues breakdown
        story.extend(self._build_issues_breakdown(data))
        
        # Tool coverage
        story.extend(self._build_tool_coverage(data))
        
        # Issues details (if any)
        if data.issues:
            story.extend(self._build_issues_details(data))
        
        # Recommendations
        story.extend(self._build_recommendations(data))
        
        # Footer
        story.extend(self._build_footer(data))
        
        # Build PDF
        doc.build(story)
        
        pdf_content = buffer.getvalue()
        buffer.close()
        
        logger.info(f"📄 Generated PDF report: {len(pdf_content)} bytes")
        return pdf_content
    
    def _build_header(self, data: ReportData) -> List:
        """Build the report header."""
        elements = []
        
        # Title
        elements.append(Paragraph(
            "🛡️ Pre-Audit Clearance Certificate",
            self.styles['ReportTitle']
        ))
        
        # Subtitle with repo name
        elements.append(Paragraph(
            f"Security Scan Report for <b>{data.repo_full_name}</b>",
            self.styles['ReportSubtitle']
        ))
        
        # Horizontal line
        elements.append(HRFlowable(
            width="100%",
            thickness=2,
            color=self.COLORS["primary"],
            spaceAfter=20,
        ))
        
        return elements
    
    def _build_status_badge(self, data: ReportData) -> List:
        """Build the pass/fail status badge."""
        elements = []
        
        if data.is_clearance_passed:
            badge_color = self.COLORS["success"]
            badge_text = "✅ CLEARANCE PASSED"
            badge_subtitle = "No Critical or High severity issues found"
        else:
            badge_color = self.COLORS["danger"]
            badge_text = "❌ CLEARANCE FAILED"
            badge_subtitle = f"{data.issues_summary.blocking} blocking issue(s) require attention"
        
        # Create badge table
        badge_data = [
            [Paragraph(f"<b>{badge_text}</b>", self.styles['BadgeText'])],
            [Paragraph(badge_subtitle, ParagraphStyle(
                'BadgeSubtitle',
                parent=self.styles['Normal'],
                fontSize=10,
                textColor=colors.white,
                alignment=TA_CENTER,
            ))],
        ]
        
        badge_table = Table(badge_data, colWidths=[4*inch])
        badge_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), badge_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('LEFTPADDING', (0, 0), (-1, -1), 20),
            ('RIGHTPADDING', (0, 0), (-1, -1), 20),
            ('ROUNDEDCORNERS', [10, 10, 10, 10]),
        ]))
        
        # Center the badge
        wrapper = Table([[badge_table]], colWidths=[6.5*inch])
        wrapper.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        
        elements.append(wrapper)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _build_summary_section(self, data: ReportData) -> List:
        """Build the scan summary section."""
        elements = []
        
        elements.append(Paragraph("📋 Scan Summary", self.styles['SectionHeader']))
        
        # Summary table
        summary_data = [
            ["Repository", data.repo_full_name],
            ["Branch", data.branch],
            ["Commit", data.commit_sha[:8] if len(data.commit_sha) > 8 else data.commit_sha],
            ["Scan Date", data.scan_date.strftime("%Y-%m-%d %H:%M UTC")],
            ["Duration", f"{data.scan_duration_seconds:.1f} seconds"],
            ["Files Scanned", str(data.files_scanned)],
            ["Solidity Version", data.solidity_version],
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), self.COLORS["light"]),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), self.COLORS["dark"]),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _build_issues_breakdown(self, data: ReportData) -> List:
        """Build the issues breakdown section."""
        elements = []
        
        elements.append(Paragraph("📊 Issues Breakdown", self.styles['SectionHeader']))
        
        # Issues count table
        severity_colors = {
            "Critical": self.COLORS["critical"],
            "High": self.COLORS["high"],
            "Medium": self.COLORS["medium"],
            "Low": self.COLORS["low"],
            "Informational": self.COLORS["info"],
        }
        
        issues_data = [["Severity", "Count", "Status"]]
        
        for severity, count in data.issues_summary.to_dict().items():
            status = "⚠️ Blocking" if severity in ["Critical", "High"] and count > 0 else "✅ OK"
            issues_data.append([severity, str(count), status])
        
        # Add total row
        issues_data.append(["Total", str(data.issues_summary.total), ""])
        
        issues_table = Table(issues_data, colWidths=[2*inch, 1.5*inch, 2*inch])
        
        # Build table style
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["primary"]),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), self.COLORS["light"]),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]
        
        # Add severity row colors
        for i, (severity, _) in enumerate(data.issues_summary.to_dict().items(), start=1):
            color = severity_colors.get(severity, self.COLORS["muted"])
            # Light tint of the severity color
            table_style.append(('BACKGROUND', (0, i), (0, i), color))
            table_style.append(('TEXTCOLOR', (0, i), (0, i), colors.white))
        
        issues_table.setStyle(TableStyle(table_style))
        
        elements.append(issues_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _build_tool_coverage(self, data: ReportData) -> List:
        """Build the tool coverage section."""
        elements = []
        
        elements.append(Paragraph("🔧 Analysis Tools Used", self.styles['SectionHeader']))
        
        if not data.tools_used:
            elements.append(Paragraph(
                "No tools information available.",
                self.styles['Normal']
            ))
        else:
            tools_data = [["Tool", "Status"]]
            for tool in data.tools_used:
                tools_data.append([tool, "✅ Completed"])
            
            tools_table = Table(tools_data, colWidths=[3*inch, 2.5*inch])
            tools_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.COLORS["primary"]),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, self.COLORS["light"]),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, self.COLORS["light"]]),
            ]))
            
            elements.append(tools_table)
        
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _build_issues_details(self, data: ReportData) -> List:
        """Build detailed issues section."""
        elements = []
        
        elements.append(Paragraph("🔍 Issue Details", self.styles['SectionHeader']))
        
        severity_emoji = {
            "Critical": "🟣",
            "High": "🔴",
            "Medium": "🟠",
            "Low": "🟡",
            "Informational": "🔵",
        }
        
        for i, issue in enumerate(data.issues[:20], start=1):  # Limit to 20 issues
            severity = issue.get("severity", "Unknown")
            emoji = severity_emoji.get(severity, "⚪")
            issue_type = issue.get("type", "Unknown Issue")
            file_info = f"{issue.get('file', 'Unknown')}:{issue.get('line', 0)}"
            tool = issue.get("tool", "Unknown")
            description = issue.get("description", "No description available.")
            
            # Truncate long descriptions
            if len(description) > 300:
                description = description[:300] + "..."
            
            elements.append(Paragraph(
                f"{emoji} <b>{i}. [{severity}] {issue_type}</b> <font color='gray'>[{tool}]</font>",
                self.styles['IssueTitle']
            ))
            
            elements.append(Paragraph(
                f"<b>File:</b> {file_info}",
                self.styles['IssueBody']
            ))
            
            elements.append(Paragraph(
                description.replace("\n", "<br/>"),
                self.styles['IssueBody']
            ))
            
            elements.append(Spacer(1, 5))
        
        if len(data.issues) > 20:
            elements.append(Paragraph(
                f"<i>... and {len(data.issues) - 20} more issues. See full report for details.</i>",
                self.styles['IssueBody']
            ))
        
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _build_recommendations(self, data: ReportData) -> List:
        """Build recommendations section."""
        elements = []
        
        elements.append(Paragraph("💡 Recommendations", self.styles['SectionHeader']))
        
        if data.is_clearance_passed:
            recommendations = [
                "✅ Your code has passed automated security checks.",
                "📋 Consider proceeding with a professional human audit.",
                "🔄 Continue running scans on every PR to maintain security posture.",
                "📚 Review the medium/low severity issues for potential improvements.",
            ]
        else:
            recommendations = [
                "🔴 Address all Critical and High severity issues before proceeding.",
                "📖 Review the suggested fixes provided for each issue.",
                "🔄 Re-run the scan after making fixes to verify resolution.",
                "💬 Consider consulting with a security expert for complex issues.",
            ]
        
        for rec in recommendations:
            elements.append(Paragraph(f"• {rec}", self.styles['Normal']))
            elements.append(Spacer(1, 5))
        
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _build_footer(self, data: ReportData) -> List:
        """Build the report footer."""
        elements = []
        
        elements.append(HRFlowable(
            width="100%",
            thickness=1,
            color=self.COLORS["light"],
            spaceBefore=20,
            spaceAfter=10,
        ))
        
        elements.append(Paragraph(
            f"Generated by <b>Audit Pit-Crew</b> on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            self.styles['Footer']
        ))
        
        elements.append(Paragraph(
            "This report is generated by automated security analysis tools. "
            "It does not replace a comprehensive human security audit.",
            self.styles['Footer']
        ))
        
        elements.append(Paragraph(
            "© 2025 Audit Pit-Crew | https://github.com/athanase-matabaro/audit-pit-crew",
            self.styles['Footer']
        ))
        
        return elements


def generate_sample_report() -> bytes:
    """Generate a sample report for testing."""
    from datetime import datetime
    
    data = ReportData(
        repo_owner="example",
        repo_name="my-defi-protocol",
        scan_date=datetime.utcnow(),
        commit_sha="abc123def456",
        branch="main",
        tools_used=["Slither", "Mythril"],
        issues_summary=IssuesSummary(
            critical=0,
            high=0,
            medium=2,
            low=3,
            informational=1,
        ),
        issues=[
            {
                "tool": "Slither",
                "type": "unchecked-transfer",
                "severity": "Medium",
                "confidence": "High",
                "description": "The return value of token.transfer() is not checked.",
                "file": "contracts/Token.sol",
                "line": 42,
            },
            {
                "tool": "Mythril",
                "type": "Integer Overflow",
                "severity": "Medium",
                "confidence": "Medium",
                "description": "Integer overflow possible in arithmetic operation.",
                "file": "contracts/Math.sol",
                "line": 15,
            },
        ],
        scan_duration_seconds=12.5,
        files_scanned=5,
        solidity_version="0.8.20",
    )
    
    generator = PreAuditReportGenerator()
    return generator.generate(data)
