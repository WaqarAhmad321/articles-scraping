from articles_scraper.utils.language import detect_language


def test_english():
    assert detect_language("The economy is in deep trouble.") == "English"


def test_urdu():
    assert detect_language("معیشت گہرے بحران میں ہے۔") == "Urdu"


def test_mixed_mostly_english():
    text = "Imran Khan (عمران خان) was arrested today in a high-profile case in Islamabad."
    assert detect_language(text) == "English"


def test_mixed_mostly_urdu():
    text = "PTI کے سربراہ عمران خان کو آج اسلام آباد میں گرفتار کر لیا گیا۔"
    assert detect_language(text) == "Urdu"


def test_empty():
    assert detect_language("") == "English"
    assert detect_language("12345 !!!") == "English"
