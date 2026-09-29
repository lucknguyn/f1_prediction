"""Smoke test giao diện thật từ artifact đã chạy, không giả metric."""
import pytest
from streamlit.testing.v1 import AppTest

from f1lab.db import ROOT


@pytest.mark.skipif(not (ROOT / "artifacts" / "latest.json").exists(), reason="Cần train trước khi test web")
def test_all_pages_render(request):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    assert not app.exception
    if request.config.getoption("--live-db"):
        assert any("MySQL đã kết nối" in box.value for box in app.sidebar.success)
    for page in ["Dự đoán & đối chiếu", "So sánh mô hình", "Dữ liệu & MySQL", "Học & bảo vệ"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, f"Page failed: {page}"


@pytest.mark.skipif(not (ROOT / "artifacts" / "latest.json").exists(), reason="Cần train trước khi test web")
def test_live_inference_and_missing_q(request):
    if not request.config.getoption("--live-db"):
        pytest.skip("Dùng --live-db để kiểm tra lưu prediction vào MySQL")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    app.sidebar.radio[0].set_value("Dự đoán & đối chiếu").run()
    app.radio(key="prediction_mode").set_value("Chạy dự đoán từ Q hiện có").run()
    app.selectbox(key="forecast_race").set_value(202602).run()
    app.button[0].click().run()
    assert not app.exception
    assert not app.error
    assert len(app.dataframe[0].value) == 22
    # Chọn race cuối mùa chưa có Q trong snapshot: không được phát sinh dự đoán giả.
    future = app.selectbox(key="forecast_race").options[-1]
    app.selectbox(key="forecast_race").select(future).run()
    app.button[0].click().run()
    assert not app.exception
    assert any("chưa có Q" in item.value for item in app.warning)
