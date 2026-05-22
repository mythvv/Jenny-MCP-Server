"""
交叉验证: 对比 ziwei2 与原版 ziwei 输出
"""

import sys
import json
import asyncio

sys.path.insert(0, "/root/jenny-droid/mcp-server")

from toolkits.ziwei2 import Ziwei as NewZiwei
from toolkits.ziwei import ZiweiToolkit

old_tk = ZiweiToolkit()

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


def compare_chart(old, new, label):
    errors = []
    for key in ["solar_date", "lunar_date", "chinese_date", "zodiac", "five_elements_class"]:
        if old.get(key) != new.get(key):
            errors.append(f"  {key}: old={old.get(key)} new={new.get(key)}")

    # 命宫身宫
    for pk in ["soul_palace", "body_palace"]:
        o = old.get(pk, {})
        n = new.get(pk, {})
        if o.get("ganzhi") != n.get("ganzhi") or o.get("index") != n.get("index"):
            errors.append(f"  {pk}: old={o} new={n}")

    # 十二宫
    old_palaces = old.get("palaces", [])
    new_palaces = new.get("palaces", [])
    if len(old_palaces) != len(new_palaces):
        errors.append(f"  palaces count: old={len(old_palaces)} new={len(new_palaces)}")
    else:
        for i, (op, np_) in enumerate(zip(old_palaces, new_palaces)):
            for k in ["name", "ganzhi", "is_body_palace", "changsheng12", "is_empty"]:
                if op.get(k) != np_.get(k):
                    errors.append(f"  palaces[{i}].{k}: old={op.get(k)} new={np_.get(k)}")
            # 主星数量
            om = [s["name"] for s in op.get("major_stars", [])]
            nm = [s["name"] for s in np_.get("major_stars", [])]
            if om != nm:
                errors.append(f"  palaces[{i}] major_stars: old={om} new={nm}")

    if errors:
        print(f"FAIL {label}")
        for e in errors:
            print(e)
        return False
    print(f"PASS {label}")
    return True


async def test_chart():
    print("\n=== 排盘 ===")
    passed = 0
    for bd, bt, g in TEST_CASES:
        label = f"chart {bd} {bt} {g}"
        try:
            old = await old_tk.ziwei_chart(bd, bt, g)
            new = NewZiwei(bd, bt, g).chart()
            if "error" in old:
                print(f"SKIP {label} (old error: {old['error']})")
                continue
            if compare_chart(old, new, label):
                passed += 1
        except Exception as e:
            print(f"ERROR {label}: {e}")
            import traceback
            traceback.print_exc()
    total = len(TEST_CASES)
    print(f"\n结果: {passed}/{total} passed")
    return passed == total


async def test_palace():
    print("\n=== 宫位分析 ===")
    passed = 0
    count = 0
    for bd, bt, g in TEST_CASES[:4]:
        for pn in ["命宫", "财帛宫", "官禄宫"]:
            label = f"palace {bd} {pn}"
            try:
                old = await old_tk.ziwei_palace(bd, bt, g, pn)
                new = NewZiwei(bd, bt, g).palace(pn)
                if "error" in old:
                    continue
                count += 1
                ok = True
                for k in ["palace_name", "ganzhi", "changsheng12"]:
                    if old.get(k) != new.get(k):
                        print(f"FAIL {label}: {k} old={old.get(k)} new={new.get(k)}")
                        ok = False
                if ok:
                    print(f"PASS {label}")
                    passed += 1
            except Exception as e:
                print(f"ERROR {label}: {e}")
    print(f"\n结果: {passed}/{count} passed")
    return passed == count


async def test_daxian():
    print("\n=== 大限 ===")
    passed = 0
    for bd, bt, g in TEST_CASES:
        label = f"daxian {bd} {g}"
        try:
            old = await old_tk.ziwei_daxian(bd, bt, g)
            new = NewZiwei(bd, bt, g).daxian()
            if "error" in old:
                continue
            old_dx = old.get("daxian", [])
            new_dx = new.get("daxian", [])
            if len(old_dx) != len(new_dx):
                print(f"FAIL {label}: count old={len(old_dx)} new={len(new_dx)}")
                continue
            ok = True
            for i, (od, nd) in enumerate(zip(old_dx, new_dx)):
                for k in ["range", "ganzhi", "palace"]:
                    if od.get(k) != nd.get(k):
                        print(f"FAIL {label}[{i}].{k}: old={od.get(k)} new={nd.get(k)}")
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
            old = await old_tk.ziwei_liunian(bd, bt, g, 2026)
            new = NewZiwei(bd, bt, g).liunian(2026)
            if "error" in old:
                continue
            ok = True
            for k in ["target_year", "age", "nominal_age"]:
                if old.get(k) != new.get(k):
                    print(f"FAIL {label}: {k} old={old.get(k)} new={new.get(k)}")
                    ok = False
            if old.get("yearly", {}).get("ganzhi") != new.get("yearly", {}).get("ganzhi"):
                print(f"FAIL {label}: yearly.gz old={old.get('yearly',{}).get('ganzhi')} new={new.get('yearly',{}).get('ganzhi')}")
                ok = False
            if ok:
                print(f"PASS {label}")
                passed += 1
        except Exception as e:
            print(f"ERROR {label}: {e}")
            import traceback
            traceback.print_exc()
    print(f"\n结果: {passed}/{len(TEST_CASES)} passed")
    return passed == len(TEST_CASES)


async def main():
    ok1 = await test_chart()
    ok2 = await test_palace()
    ok3 = await test_daxian()
    ok4 = await test_liunian()

    print("\n" + "=" * 50)
    if ok1 and ok2 and ok3 and ok4:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
