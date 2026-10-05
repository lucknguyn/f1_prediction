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
    for page in ["Dự đoán", "Phân tích", "Mô hình", "Dữ liệu"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, f"Page failed: {page}"


@pytest.mark.skipif(not (ROOT / "artifacts" / "latest.json").exists(), reason="Cần train trước khi test web")
def test_live_inference_and_missing_q(request):
    if not request.config.getoption("--live-db"):
        pytest.skip("Dùng --live-db để kiểm tra lưu prediction vào MySQL")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    app.sidebar.radio[0].set_value("Dự đoán").run()
    app.radio(key="prediction_scope").set_value("Q → Race (đối chứng)").run()
    app.radio(key="prediction_mode").set_value("Chạy dự đoán từ Q hiện có").run()
    app.selectbox(key="forecast_race").set_value(202602).run()
    next(button for button in app.button if button.label == "Tạo và lưu dự đoán").click().run()
    assert not app.exception
    assert not app.error
    assert len(app.dataframe[0].value) == 22
    # Chọn race cuối mùa chưa có Q trong snapshot: không được phát sinh dự đoán giả.
    future = app.selectbox(key="forecast_race").options[-1]
    app.selectbox(key="forecast_race").select(future).run()
    next(button for button in app.button if button.label == "Tạo và lưu dự đoán").click().run()
    assert not app.exception
    assert any("chưa có Q" in item.value for item in app.warning)


@pytest.mark.skipif(not (ROOT / "artifacts/weekend/latest.json").exists(), reason="Cần huấn luyện từng phiên")
def test_weekend_prediction_saved_in_mysql(request):
    if not request.config.getoption("--live-db"):
        pytest.skip("Cần MySQL thật")
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
    app.sidebar.radio[0].set_value("Dự đoán").run()
    app.selectbox(key="weekend_race").set_value(202616).run()
    app.selectbox(key="weekend_session").set_value("202616-R").run()
    app.button(key="predict_weekend").click().run()
    assert not app.exception
    assert not app.error
    assert len(app.dataframe[1].value) == 22
    # Sprint weekend Singapore: không được phát sinh FP2 hoặc FP3 giả.
    app.selectbox(key="weekend_race").set_value(202617).run()
    assert not app.exception
    assert 'FP2' not in app.selectbox(key="weekend_session").options
    assert 'FP3' not in app.selectbox(key="weekend_session").options
    app.selectbox(key="weekend_session").set_value("202617-R").run()
    app.button(key="predict_weekend").click().run()
    assert not app.exception and not app.error
    assert app.dataframe[1].value['Thực tế'].isna().all()


@pytest.mark.skipif(not (ROOT / "artifacts/latest.json").exists(), reason="Cần artifact")
def test_direct_weekend_link():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45)
    app.query_params["page"] = "weekend"
    app.run()
    assert not app.exception
    assert app.sidebar.radio[0].value == "Dự đoán"
