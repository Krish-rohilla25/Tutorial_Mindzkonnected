import fitz  # PyMuPDF


def load_normal_pdf(file_path):
    """
    Load a normal (text-based) PDF and extract all text from it.
    Uses PyMuPDF (fitz).

    Returns a single string with all the text from the PDF.
    """
    doc = fitz.open(file_path)
    all_text = ""

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        all_text += text

    doc.close()
    return all_text


def load_scanned_pdf(file_path):
    """
    Placeholder for scanned PDF support.
    Scanned PDFs are image-based, so they need OCR to extract text.

    To implement this in the future:
    1. Install: pip install pytesseract pdf2image
    2. Also install Tesseract OCR on your system (brew install tesseract on mac)
    3. Use pdf2image to convert each PDF page to an image
    4. Use pytesseract.image_to_string() on each image
    5. Concatenate and return the text

    Example:
        from pdf2image import convert_from_path
        import pytesseract

        pages = convert_from_path(file_path)
        all_text = ""
        for page in pages:
            all_text += pytesseract.image_to_string(page)
        return all_text
    """
    raise NotImplementedError(
        "Scanned PDF support is not available yet. "
        "Please upload a normal (text-based) PDF."
    )


def load_pdf(file_path, pdf_type="normal"):
    """
    Main entry point. Routes to the correct loader based on pdf_type.
    pdf_type: 'normal' or 'scanned'
    """
    if pdf_type == "normal":
        return load_normal_pdf(file_path)
    elif pdf_type == "scanned":
        return load_scanned_pdf(file_path)
    else:
        raise ValueError(f"Unknown pdf_type: {pdf_type}. Use 'normal' or 'scanned'.")
