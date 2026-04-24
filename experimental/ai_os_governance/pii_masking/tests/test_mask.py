"""PII 마스킹 round-trip 테스트."""
from __future__ import annotations

from pii_masking import mask_pii, unmask_pii


def test_phone_mask():
    src = "연락처: 010-1234-5678 입니다"
    r = mask_pii(src)
    assert "010-1234-5678" not in r.masked_text
    assert "[PHONE_REDACTED_1]" in r.masked_text
    assert unmask_pii(r.masked_text, r.mapping) == src


def test_email_mask():
    src = "메일은 aehdals123@gmail.com 입니다"
    r = mask_pii(src)
    assert "aehdals123@gmail.com" not in r.masked_text
    assert "[EMAIL_REDACTED_1]" in r.masked_text


def test_rrn_mask():
    src = "주민번호 901231-1234567 확인"
    r = mask_pii(src)
    assert "901231-1234567" not in r.masked_text
    assert "[RRN_REDACTED_1]" in r.masked_text


def test_account_mask():
    src = "계좌 110-123-456789 송금"
    r = mask_pii(src)
    assert "110-123-456789" not in r.masked_text


def test_multi_pii_roundtrip():
    src = "전화 010-1111-2222, 이메일 a@b.com, 계좌 110-123-456789"
    r = mask_pii(src)
    restored = unmask_pii(r.masked_text, r.mapping)
    assert restored == src
    assert len(r.mapping) == 3
