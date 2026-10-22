from scripts.run_pytest_windows import normalize_directory_mode


def test_runner_relaxes_only_private_temp_directory_mode():
    assert normalize_directory_mode(0o700) == 0o777
    assert normalize_directory_mode(0o755) == 0o755
    assert normalize_directory_mode(0o600) == 0o600
