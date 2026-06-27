"""Tests for src/certificate.py — PDF certificate generation."""
import os

from src import certificate, config


def test_make_certificate_creates_pdf(tmp_path, monkeypatch):
    """Certificate generation should produce a valid PDF file."""
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
    path = certificate.make_certificate("TestUser", 25, "محارب")
    assert os.path.exists(path)
    assert path.endswith(".pdf")
    # PDF should start with %PDF
    with open(path, "rb") as f:
        header = f.read(5)
    assert header == b"%PDF-"


def test_make_certificate_arabic_name(tmp_path, monkeypatch):
    """Should handle Arabic names without crashing."""
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
    path = certificate.make_certificate("محمد أحمد", 30, "بطل المرونة")
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0


def test_make_certificate_special_chars(tmp_path, monkeypatch):
    """Names with special characters should be sanitized for filename."""
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
    path = certificate.make_certificate("user/name<>|", 10, "مثابر")
    assert os.path.exists(path)
    # Filename should not contain the special chars
    basename = os.path.basename(path)
    assert "/" not in basename
    assert "<" not in basename
