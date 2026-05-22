"""
交叉验证: 对比 bazi2 与原版 bazi 输出
"""

import sys
import json
import asyncio

sys.path.insert(0, "/root/jenny-droid/mcp-server")

from toolkits.bazi2 import Bazi as NewBazi
from toolkits.bazi import BaziToolkit

old_tk = BaziToolkit()

TEST_CASES = [
    ("1990-05-15", "14:30", "男"),
    ("1985-11-20", "08:00", "女"),
    ("2000-01-01", "00:00", "男"),
    ("1999-12-31", "23:00", "女"),
    ("1975-03-08", "06:30", "男"),
    ("2003-07-22", "12:00", "女"),
    ("1988-10-10", "18:45", "男"),
    ("1995-06-01", "04:15", "女"),
]


async def test_chart():
    print("\n=== 排盘 ===")
    passed = 0
    for bd, bt, g in TEST_CASES:
        label = f"chart {bd} {bt} {g}"
        try:
            old = await old_tk.bazi_chart(bd, bt, g)
            new = NewBazi(bd, bt, g).chart()
            if "error" in old:
                print(f"SKIP {label} (old error)")
                continue

            ok = True
            errors = []

            # 四柱
            old_pillars = old.get("four_pillars", [])
            new_pillars = new.get("four_pillars", [])
            if len(old_pillars) != len(new_pillars):
                errors.append(f"  pillars count: old={len(old_pillars)} new={len(new_pillars)}")
            for i, (op, np) in enumerate(zip(old_pillars, new_pillars)):
                for k in ["ganzhi", "tian_gan", "di_zhi", "na_yin", "hide_gan"]:
                    if op.get(k) != np.get(k):
                        errors.append(f"  pillar[{i}].{k}: old={op.get(k)} new={np.get(k)}")

            # 日主
            old_dm = old.get("day_master", {})
            new_dm = new.get("day_master", {})
            for k in ["gan", "element"]:
                if old_dm.get(k) != new_dm.get(k):
                    errors.append(f"  day_master.{k}: old={old_dm.get(k)} new={new_dm.get(k)}")

            # 胎元/命宫
            for k in ["ming_gong", "shen_gong", "tai_yuan", "tai_xi"]:
                if old.get(k) != new.get(k):
                    errors.append(f"  {k}: old={old.get(k)} new={new.get(k)}")

            if errors:
                print(f"FAIL {label}")
                for e in errors:
                    print(e)
            else:
                print(f"PASS {label}")
                passed += 1
        except Exception as e:
            print(f"ERROR {label}: {e}")
            import traceback
            traceback.print_exc()
    print(f"\n结果: {passed}/{len(TEST_CASES)} passed")
    return passed == len(TEST_CASES)


async def test_wuxing():
    print("\n=== 五行分析 ===")
    passed = 0
    for bd, bt, g in TEST_CASES:
        label = f"wuxing {bd}"
        try:
            old = await old_tk.bazi_wuxing(bd, bt)
            new = NewBazi(bd, bt, g).wuxing()
            if "error" in old:
                continue

            ok = True
            for k in ["day_master", "day_master_element", "missing", "strong"]:
                if old.get(k) != new.get(k):
                    print(f"FAIL {label}: {k} old={old.get(k)} new={new.get(k)}")
                    ok = False
            # distribution counts
            old_dist = old.get("element_distribution", {})
            new_dist = new.get("element_distribution", {})
            for elem in "木火土金水":
                oc = old_dist.get(elem, {}).get("count", 0)
                nc = new_dist.get(elem, {}).get("count", 0)
                if oc != nc:
                    print(f"FAIL {label}: {elem} count old={oc} new={nc}")
                    ok = False
            if ok:
                print(f"PASS {label}")
                passed += 1
        except Exception as e:
            print(f"ERROR {label}: {e}")
    print(f"\n结果: {passed}/{len(TEST_CASES)} passed")
    return passed == len(TEST_CASES)


async def test_dayun():
    print("\n=== 大运 ===")
    passed = 0
    for bd, bt, g in TEST_CASES:
        label = f"dayun {bd} {g}"
        try:
            old = await old_tk.bazi_dayun(bd, bt, g)
            new = NewBazi(bd, bt, g).dayun()
            if "error" in old:
                continue

            ok = True
            for k in ["start_age", "direction"]:
                if old.get(k) != new.get(k):
                    print(f"FAIL {label}: {k} old={old.get(k)} new={new.get(k)}")
                    ok = False
            old_dy = old.get("dayun", [])
            new_dy = new.get("dayun", [])
            if len(old_dy) != len(new_dy):
                print(f"FAIL {label}: count old={len(old_dy)} new={len(new_dy)}")
                ok = False
            else:
                for i, (od, nd) in enumerate(zip(old_dy, new_dy)):
                    if od.get("ganzhi") != nd.get("ganzhi"):
                        print(f"FAIL {label}[{i}]: gz old={od.get('ganzhi')} new={nd.get('ganzhi')}")
                        ok = False
            if ok:
                print(f"PASS {label}")
                passed += 1
        except Exception as e:
            print(f"ERROR {label}: {e}")
    print(f"\n结果: {passed}/{len(TEST_CASES)} passed")
    return passed == len(TEST_CASES)


async def test_liunian():
    print("\n=== 流年 ===")
    passed = 0
    for bd, bt, g in TEST_CASES:
        label = f"liunian {bd} {g}"
        try:
            old = await old_tk.bazi_liunian(bd, bt, g, 2026)
            new = NewBazi(bd, bt, g).liunian(2026)
            if "error" in old:
                continue

            ok = True
            for k in ["target_year", "age", "year_ganzhi", "year_gan", "year_zhi",
                       "year_element", "current_dayun", "day_master"]:
                if old.get(k) != new.get(k):
                    print(f"FAIL {label}: {k} old={old.get(k)} new={new.get(k)}")
                    ok = False
            if ok:
                print(f"PASS {label}")
                passed += 1
        except Exception as e:
            print(f"ERROR {label}: {e}")
    print(f"\n结果: {passed}/{len(TEST_CASES)} passed")
    return passed == len(TEST_CASES)


async def main():
    ok1 = await test_chart()
    ok2 = await test_wuxing()
    ok3 = await test_dayun()
    ok4 = await test_liunian()

    print("\n" + "=" * 50)
    if ok1 and ok2 and ok3 and ok4:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
