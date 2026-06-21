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
    Load a scanned (image-based) PDF and extract text using OCR.

    Uses pdf2image to convert each page to a high-resolution image, applies
    grayscale + contrast preprocessing using PIL, then runs pytesseract OCR.
    Higher DPI and preprocessing significantly improve accuracy on letterheads,
    stamps, and mixed-layout scanned documents.

    Returns a single string with all the OCR-extracted text.
    """
    from pdf2image import convert_from_path
    import pytesseract
    from PIL import ImageFilter, ImageEnhance

    pages = convert_from_path(file_path, dpi=300)
    all_text = ""

    for page in pages:
        page = page.convert("L")

        page = ImageEnhance.Contrast(page).enhance(2.0)

        page = page.filter(ImageFilter.SHARPEN)

        text = pytesseract.image_to_string(page)
        all_text += text + "\n"

    # Save raw OCR output to a file for debugging
    debug_path = "./rag_application/ocr_debug.txt"
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(all_text)

    return all_text



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

