"""Unit test for end-to-end DataManager facade initialization, status, reload, and shutdown."""

from router.application.data.data_manager import DataManager


def test_data_manager_lifecycle(dataset_dir: str) -> None:
    """Verify DataManager initialization, record counts, reload, and shutdown."""
    dm = DataManager(dataset_dir=dataset_dir)
    assert dm.get_status()["initialized"] is False

    # Initialize
    dm.initialize()
    status = dm.get_status()
    assert status["initialized"] is True
    assert status["status"] == "healthy"
    assert status["counts"]["users"] > 0
    assert status["counts"]["groups"] > 0
    assert status["counts"]["businesses"] > 0
    assert status["counts"]["messages"] > 0

    # Reload
    dm.reload()
    assert dm.get_status()["initialized"] is True

    # Shutdown
    dm.shutdown()
    assert dm.get_status()["initialized"] is False
