"""Report rendering for human consumption.

Distinct from the markdown the agents exchange with each other: that stays
plain text because it is prompt input. Everything here is for a person to
read or download.
"""

from .pdf import build_run_pdf, run_pdf_filename

__all__ = ["build_run_pdf", "run_pdf_filename"]
