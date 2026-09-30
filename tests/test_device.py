"""Tests des informations Android extraites sans contacter un emulateur."""
from cemankill.device import foreground_package


def test_foreground_package_uses_top_resumed_activity():
    dump = "topResumedActivity=ActivityRecord{7d515a2 u0 com.ffprod.cemanty/fr.cemanty.MainActivity t15}"
    assert foreground_package(dump) == "com.ffprod.cemanty"


def test_foreground_package_detects_play_store():
    dump = "mResumedActivity=ActivityRecord{12ab u0 com.android.vending/com.google.android.finsky.MainActivity t13}"
    assert foreground_package(dump) == "com.android.vending"


def test_foreground_package_falls_back_to_current_window():
    window = "mCurrentFocus=Window{123abc u0 com.android.chrome/com.google.android.apps.chrome.Main}"
    assert foreground_package("", window) == "com.android.chrome"


def test_foreground_package_returns_empty_when_unreadable():
    assert foreground_package("sortie inattendue", "") == ""
