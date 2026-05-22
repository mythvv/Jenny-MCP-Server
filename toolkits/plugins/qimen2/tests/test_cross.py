"""
交叉验证: 对比 qimen2 与 kinqimen 原版输出
"""

import sys
import os

# 确保可以导入 kinqimen
_kq_path = "/root/jenny-droid/mcp-server/.venv/lib/python3.13/site-packages/kinqimen"
if _kq_path not in sys.path:
    sys.path.insert(0, _kq_path)

# 先导入 qimen2
sys.path.insert(0, "/root/jenny-droid/mcp-server")

from toolkits.qimen2 import Qimen as NewQimen

# 导入原版 kinqimen (需要 patch)
import kinqimen as _qm_mod
import config as _config

# Patch pan_sky_minute
if not getattr(_qm_mod.Qimen, '_sky_minute_patched', False):
    _orig = _qm_mod.Qimen.pan_sky_minute
    def _safe(self, option):
        result = _orig(self, option)
        if result is None:
            result = self.pan_sky(option)
        return result
    _qm_mod.Qimen.pan_sky_minute = _safe
    _qm_mod.Qimen._sky_minute_patched = True

OldQimen = _qm_mod.Qimen


# ── 测试用例 ──

TEST_CASES = [
    (2026, 5, 20, 13, 38),
    (2026, 5, 20, 10, 30),
    (2026, 5, 20, 14, 20),
    (2026, 6, 15, 14, 20),
    (2000, 1, 1, 0, 0),
    (2026, 12, 31, 23, 59),
    (2024, 5, 12, 23, 7),
    (2024, 2, 2, 4, 15),
    (2025, 3, 15, 9, 30),
    (2025, 7, 20, 15, 45),
    (2025, 11, 10, 11, 0),
    (2026, 1, 5, 3, 20),
]


def normalize_sky(sky):
    """统一天盘格式为 dict"""
    if isinstance(sky, tuple):
        return sky[0]
    return sky


def compare_pan(old, new, label):
    """对比两个 pan 结果"""
    errors = []

    # 地盘
    old_earth = old.get("地盤", {})
    new_earth = new.get("地盤", {})
    if old_earth != new_earth:
        errors.append(f"  地盤不一致: old={old_earth} new={new_earth}")

    # 天盘
    old_sky = normalize_sky(old.get("天盤", {}))
    new_sky = normalize_sky(new.get("天盤", {}))
    if old_sky != new_sky:
        errors.append(f"  天盤不一致:\n    old={old_sky}\n    new={new_sky}")

    # 门
    old_door = old.get("門", {})
    new_door = new.get("門", {})
    if old_door != new_door:
        errors.append(f"  門不一致: old={old_door} new={new_door}")

    # 星
    old_star = old.get("星", {})
    new_star = new.get("星", {})
    if old_star != new_star:
        errors.append(f"  星不一致: old={old_star} new={new_star}")

    # 神
    old_god = old.get("神", {})
    new_god = new.get("神", {})
    if old_god != new_god:
        errors.append(f"  神不一致: old={old_god} new={new_god}")

    # 局
    old_ju = old.get("排局", "")
    new_ju = new.get("排局", "")
    if old_ju != new_ju:
        errors.append(f"  排局不一致: old={old_ju} new={new_ju}")

    # 节气
    old_jq = old.get("節氣", "")
    new_jq = new.get("節氣", "")
    if old_jq != new_jq:
        errors.append(f"  節氣不一致: old={old_jq} new={new_jq}")

    # 干支
    old_gz = old.get("干支", "")
    new_gz = new.get("干支", "")
    if old_gz != new_gz:
        errors.append(f"  干支不一致: old={old_gz} new={new_gz}")

    # 旬首
    old_xs = old.get("旬首", "")
    new_xs = new.get("旬首", "")
    if old_xs != new_xs:
        errors.append(f"  旬首不一致: old={old_xs} new={new_xs}")

    if errors:
        print(f"FAIL {label}")
        for e in errors:
            print(e)
        return False
    else:
        print(f"PASS {label}")
        return True


def test_pan_chaibu():
    """测试拆补法"""
    print("\n=== 时家奇门 (拆补法) ===")
    passed = 0
    failed = 0
    for y, m, d, h, mi in TEST_CASES:
        label = f"pan(拆补) {y}-{m}-{d} {h}:{mi}"
        try:
            old = OldQimen(y, m, d, h, mi).pan(1)
            new = NewQimen(y, m, d, h, mi).pan(1)
            if compare_pan(old, new, label):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"ERROR {label}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n结果: {passed} passed, {failed} failed")
    return failed == 0


def test_pan_zhirun():
    """测试置闰法"""
    print("\n=== 时家奇门 (置闰法) ===")
    passed = 0
    failed = 0
    for y, m, d, h, mi in TEST_CASES:
        label = f"pan(置闰) {y}-{m}-{d} {h}:{mi}"
        try:
            old = OldQimen(y, m, d, h, mi).pan(2)
            new = NewQimen(y, m, d, h, mi).pan(2)
            if compare_pan(old, new, label):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"ERROR {label}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n结果: {passed} passed, {failed} failed")
    return failed == 0


def test_pan_minute():
    """测试刻家奇门"""
    print("\n=== 刻家奇门 ===")
    passed = 0
    failed = 0
    for y, m, d, h, mi in TEST_CASES:
        label = f"pan_minute {y}-{m}-{d} {h}:{mi}"
        try:
            old = OldQimen(y, m, d, h, mi).pan_minute(1)
            new = NewQimen(y, m, d, h, mi).pan_minute(1)
            if compare_pan(old, new, label):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"ERROR {label}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n结果: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    ok1 = test_pan_chaibu()
    ok2 = test_pan_zhirun()
    ok3 = test_pan_minute()

    print("\n" + "=" * 50)
    if ok1 and ok2 and ok3:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
        sys.exit(1)
