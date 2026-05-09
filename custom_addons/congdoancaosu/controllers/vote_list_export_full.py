import json
import io
import sys

from odoo import http
from odoo.http import request

from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4, portrait
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class Binary(http.Controller):
    @http.route(
        "/web/binary/vote_list_export_full/<vote_list_ids>",
        type="http",
        auth="user",
        website=True,
    )
    def export_vote_list_full_as_pdf(self, **kwargs):
        vote_list_ids = json.loads(kwargs.get("vote_list_ids"))
        vote_lists = request.env["congdoan.baucu.vote_list"].browse(vote_list_ids)
        # Register the Times New Roman font
        pdfmetrics.registerFont(TTFont('TimesNewRoman', self.get_normal_font_path()))
        pdfmetrics.registerFont(TTFont('TimesNewRoman-Bold', self.get_bold_font_path()))

        # Create a PDF buffer using StringIO
        pdf_buffer = io.BytesIO()

        # Create a new PDF document with margins
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=portrait(A4),
            leftMargin=0.5 * cm, rightMargin=0.5 * cm,
            topMargin=0.5 * cm, bottomMargin=0.5 * cm
        )

        # Define styles for the title and table
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        title_style.fontName = 'TimesNewRoman-Bold'  # Use Times New Roman
        title_style.alignment = 1  # Center alignment
        title_style.fontSize = 40
        title_style.spaceAfter = 2 * cm

        normal_style = styles['Normal']
        normal_style.fontName = 'TimesNewRoman'
        normal_style.fontSize = 15
        normal_style.alignment = 1
        normal_style.leading = 20

        header_style = ParagraphStyle(
            name='HeaderStyle',
            parent=styles['Normal'],
            fontName='TimesNewRoman-Bold',
            fontSize=18,  # Set font size to 20
            alignment=1,  # Center alignment
            leading=20,  # Vertical spacing for the header row (font size + 4)

        )

        # Create story elements
        elements = []

        for vote_list in vote_lists:
            # Add the title to the PDF
            title = Paragraph(vote_list.name.upper(), title_style)
            elements.append(title)

            # Create table data
            table_data = [[Paragraph(item, header_style) for item in ["STT", "Họ Tên", "Chức vụ/ Chức danh", "Số phiếu bầu", "Tỷ lệ"]]]
            vote_details = vote_list.get_vote_details_for_full_export()
            table_data.extend(
                [
                    Paragraph(str(order), normal_style),
                    Paragraph(vote_detail["full_name"], normal_style),
                    Paragraph(vote_detail["job_title"], normal_style),
                    Paragraph(str(vote_detail["vote"]), normal_style),
                    Paragraph(f'{vote_detail["rate"]}%', normal_style),
                ]
                for order, vote_detail in enumerate(vote_details, start=1)
            )
            # Create the table
            table = Table(table_data, colWidths=[1.8 * cm, 5 * cm, 6.7 * cm, 3 * cm, 2.5 * cm])
            table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'TimesNewRoman-Bold'),

                # ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  # Adjust spacing between title and table
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            # Add the table to the PDF
            elements.append(table)

        # Build the PDF document
        doc.build(elements)

        # Get the PDF content from the buffer
        pdf_content = pdf_buffer.getvalue()
        pdf_buffer.close()

        # Encode file_name as UTF-8
        file_name = vote_lists[0].name.encode('utf-8').decode('latin-1', 'ignore')

        # Return the PDF as a response
        return request.make_response(
            pdf_content,
            [
                (
                    "Content-Type",
                    "application/pdf",
                ),
                (
                    "Content-Disposition",
                    f"attachment; filename={file_name}.pdf",
                ),
            ],
        )

    @staticmethod
    def get_bold_font_path():
        # Detect the operating system and set the font path accordingly
        if sys.platform == 'darwin':
            # Mac
            return 'Times New Roman Bold.ttf'
        elif sys.platform == 'win32':
            # Windows
            return 'timesbd.ttf'
        else:
            # Linux (Ubuntu)
            return 'DejaVuSerif-Bold.ttf'

    @staticmethod
    def get_normal_font_path():
        # Detect the operating system and set the font path accordingly
        if sys.platform == 'darwin':
            # Mac
            return 'Times New Roman.ttf'
        elif sys.platform == 'win32':
            # Windows
            return 'times.ttf'
        else:
            # Linux (Ubuntu)
            return 'DejaVuSerif.ttf'
