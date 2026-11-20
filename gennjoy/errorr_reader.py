"""
Reader for NJOY ERRORR output tapes (MF31, MF33, MF35 multigroup covariances).

The ERRORR output tape contains, for each covariance file MF and reaction MT:
    HEAD  [ZA, AWR, 0, 0, 0, NL]
    for each of the NL sub-sections (MT1):
        CONT [0, 0, MAT1, MT1, 0, NG]
        LIST rows [0, 0, NG2, IG2LO, NG2, IG] + NG2 values  (row IG, columns IG2LO..)
The group boundaries are given in MF1/MT451. With irelco = 1 the matrices are
relative covariances.
"""
import re
import numpy as np

_NUM = re.compile(r'([0-9.])([+-])(\d+)\s*$')


def _f(s):
    s = s.strip()
    if not s:
        return 0.0
    return float(_NUM.sub(r'\1e\2\3', s))


def _fields(line):
    return [line[i:i + 11] for i in range(0, 66, 11)]


def _ctrl(line):
    try:
        return int(line[70:72]), int(line[72:75])
    except ValueError:
        return None, None


def read_errorr(path):
    """Return (group_bounds_eV, {(mf, mt, mt1): NGxNG ndarray})."""
    lines = open(path, errors='ignore').read().splitlines()
    bounds = None
    mats = {}
    i = 0
    n = len(lines)
    while i < n:
        mf, mt = _ctrl(lines[i])
        if mf == 1 and mt == 451 and bounds is None:
            f2 = _fields(lines[i + 1])
            ng = int(_f(f2[2]))
            vals = []
            j = i + 2
            while len(vals) < ng + 1:
                vals += [_f(x) for x in _fields(lines[j])]
                j += 1
            bounds = np.array(vals[:ng + 1])
            i = j
            continue
        if mf in (31, 33, 35) and mt and mt > 0:
            head = _fields(lines[i])
            nl = int(_f(head[5]))
            i += 1
            for _ in range(nl):
                c = _fields(lines[i])
                mt1 = int(_f(c[3]))
                ng = int(_f(c[5]))
                i += 1
                m = np.zeros((ng, ng))
                ig = 0
                while ig < ng:
                    l = _fields(lines[i])
                    ng2 = int(_f(l[2]))
                    ig2lo = int(_f(l[3]))
                    ig = int(_f(l[5]))
                    i += 1
                    vals = []
                    while len(vals) < ng2:
                        vals += [_f(x) for x in _fields(lines[i])]
                        i += 1
                    m[ig - 1, ig2lo - 1:ig2lo - 1 + ng2] = vals[:ng2]
                mats[(mf, mt, mt1)] = m
            continue
        i += 1
    return bounds, mats


def export_csv(path, out_prefix):
    """Write one CSV per (MF, MT, MT1) relative covariance matrix and the group bounds."""
    bounds, mats = read_errorr(path)
    written = []
    if bounds is not None:
        np.savetxt(f"{out_prefix}_group_bounds_eV.csv", bounds, delimiter=",", fmt="%.6e")
    for (mf, mt, mt1), m in sorted(mats.items()):
        mf_label = 31 if mt in (452, 455, 456) else mf   # ERRORR writes nu-bar blocks under MF33
        name = f"{out_prefix}_MF{mf_label}_MT{mt}_MT{mt1}.csv"
        np.savetxt(name, m, delimiter=",", fmt="%.6e")
        written.append(name)
    return written
