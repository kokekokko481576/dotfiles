"""
ドット絵ワニ博士のスプライト生成スクリプト(単一ソース)。

公式の見た目(大阪大学マスコット)に寄せた第2版:
- 角帽は無し(初版はClaudeの創作だった。公式はかぶっていない)
- 黄色い目+大きな黒目が頭の上のバンプに乗る
- クリーム色の腹に黒い横線(ワニの腹板)
- 白い牙・白い爪、大きなピンクの口

ここのASCIIグリッドが原本。実行すると
- static/sprites.js   (PWAがcanvas描画に使うデータ)
- static/icon-192.png / icon-512.png (PWAマニフェスト用アイコン)
- (--preview時) プレビューPNG
を生成する。スプライトを変えたいときはこのファイルを編集して再実行+コミット。

PNGは依存ライブラリなし(zlib+struct)で書き出す。
"""
import json
import struct
import sys
import zlib
from pathlib import Path

# ---- パレット ----
PALETTE = {
    ".": None,            # 透明
    "K": (16, 60, 34),     # 輪郭(濃緑)
    "G": (53, 158, 88),    # 体(緑)
    "D": (38, 120, 64),    # 体の影
    "L": (247, 244, 230),  # 腹(クリーム)
    "Y": (255, 210, 45),   # 目(黄)
    "P": (24, 24, 24),     # 瞳
    "W": (255, 255, 255),  # 牙・爪
    "R": (232, 88, 136),   # 口の中(ピンク)
    "C": (255, 150, 160),  # ほっぺ
    "Z": (122, 162, 247),  # Zzz・汗
    "*": (255, 220, 120),  # キラキラ
    # ---- 敵・小物用(小文字) ----
    "m": (156, 96, 208),   # スライム(紫)
    "n": (82, 92, 150),    # コウモリ(紺)
    "e": (208, 70, 70),    # キノコの傘(赤)
    "s": (216, 218, 232),  # おばけ(淡)
    "g": (148, 148, 158),  # ゴーレム(灰)
    "o": (205, 124, 74),   # ツボ(テラコッタ)
    "d": (152, 84, 46),    # ツボの影
}

W = 32
H = 32

# ---- ベース(ふつう: 閉じた口+牙、目ぱっちり) ----
# 32x32。行は上から。grid()が右側を透明で埋めるので末尾のドットは省略可。
BASE = [
    "",
    "........KKK..........KKK",
    ".......KYYYK........KYYYK",
    "......KYYYYYK......KYYYYYK",
    "......KYYPPYK......KYYPPYK",
    "......KYYPPYK......KYYPPYK",
    "......KYYYYYK......KYYYYYK",
    ".....KGGGGGGGGGGGGGGGGGGGGK",
    "...KGGGGGGGGGKKGGKKGGGGGGGGK",
    "...KGGGGGGGGGGGGGGGGGGGGGGGGK",
    "...KGKKKKKKKKKKKKKKKKKKKKKKGK",
    "...KGGGWWGGGWWGGGGWWGGGWWGGGK",
    "...KGGGGGGGGGGGGGGGGGGGGGGGGK",
    "....KGGGGGGGGGGGGGGGGGGGGGGK",
    "....KGGGGGGGGGGGGGGGGGGGGGGK",
    ".....KGGGGGGGGGGGGGGGGGGGGK",
    ".....KGGGGLLLLLLLLLLLLGGGGK",
    ".KGGGGGGGGLLLLLLLLLLLLGGGGGGGGK",
    ".KGGKGGGGGLLLLLLLLLLLLGGGGGKGGK",
    ".KGGKGGGGGLKKKKKKKKKKLGGGGGKGGK",
    ".KWWKGGGGGLLLLLLLLLLLLGGGGGKWWK",
    "..KK.KGGGGLLLLLLLLLLLLGGGGK.KK",
    ".....KGGGGLKKKKKKKKKKLGGGGK",
    ".....KGGGGLLLLLLLLLLLLGGGGK",
    ".....KGGGGLLLLLLLLLLLLGGGGK",
    ".....KGGGGLKKKKKKKKKKLGGGGK",
    "......KGGGGLLLLLLLLLLGGGGK",
    ".......KGGGGGGGGGGGGGGGGK",
    "........KGGK........KGGK",
    "........KGGK........KGGK",
    "......KKGGWWK......KWWGGKK",
    "......KKKKKKK......KKKKKKK",
]


def grid(rows, w=None):
    # 行長のタイプミスを許容: 規定桁に満たなければ透明で右詰め、超えたらエラー
    w = w or W
    fixed = []
    for i, r in enumerate(rows):
        if len(r) > w:
            raise ValueError(f"row {i} is {len(r)} chars (max {w}): {r}")
        fixed.append(list(r.ljust(w, ".")))
    return fixed


def to_rows(g):
    return ["".join(r) for r in g]


def put(g, y, x, s):
    for i, ch in enumerate(s):
        if ch != " ":
            g[y][x + i] = ch


def replace_row(g, y, x0, x1, ch):
    for x in range(x0, x1 + 1):
        g[y][x] = ch


def _close_eyes(g):
    """両目を閉じる(黄色をまぶたの緑に、下端にまつ毛線)。"""
    put(g, 2, 8, "GGG")
    put(g, 2, 21, "GGG")
    for y in (3, 4):
        put(g, y, 7, "GGGGG")
        put(g, y, 20, "GGGGG")
    put(g, 5, 7, "KKKKK")
    put(g, 5, 20, "KKKKK")
    put(g, 6, 7, "GGGGG")
    put(g, 6, 20, "GGGGG")
    return g


# ---- バリアント生成 ----

def frame_normal_1():
    return grid(BASE)


def frame_normal_2():
    """呼吸: 全体を1px下げる。"""
    g = grid(BASE)
    return [list("." * W)] + g[:-1]


def frame_blink():
    return _close_eyes(grid(BASE))


def _open_mouth(g):
    """口を大きく開けたピンクの笑顔(上あごに白い歯)に差し替える。"""
    put(g, 10, 4, "GKKKKKKKKKKKKKKKKKKKKKKG")
    put(g, 11, 4, "GKWWRRRRWWRRRRWWRRRRWWKG")
    put(g, 12, 4, "GGKRRRRRRRRRRRRRRRRRRKGG")
    put(g, 13, 5, "GGKKKKKKKKKKKKKKKKKKGG")
    return g


def frame_happy_1():
    g = grid(BASE)
    _open_mouth(g)
    # ほっぺ
    put(g, 9, 4, "CC")
    put(g, 9, 26, "CC")
    return g


def frame_happy_2():
    g = frame_happy_1()
    return [list("." * W)] + g[:-1]


def frame_excellent_1():
    g = frame_happy_1()
    # 側面の腕(r17-21の外側)を消して体の輪郭を閉じる
    for y in (17, 18, 19, 20):
        put(g, y, 1, "....")
        put(g, y, 5, "K")
        put(g, y, 26, "K")
        put(g, y, 27, "....")
    put(g, 21, 2, "...")
    put(g, 21, 27, "...")
    # バンザイの腕(頭の横、こぶし=白爪)
    put(g, 11, 0, "KWWK")
    put(g, 12, 0, "KGGK")
    put(g, 13, 0, "KGGK")
    put(g, 14, 1, "KGGK")
    put(g, 15, 2, "KGGK")
    put(g, 16, 3, "KGK")
    put(g, 11, 28, "KWWK")
    put(g, 12, 28, "KGGK")
    put(g, 13, 28, "KGGK")
    put(g, 14, 27, "KGGK")
    put(g, 15, 26, "KGGK")
    put(g, 16, 26, "KGK")
    # キラキラ
    put(g, 1, 2, "*")
    put(g, 4, 29, "*")
    put(g, 8, 1, "*")
    put(g, 6, 30, "*")
    return g


def frame_excellent_2():
    g = frame_excellent_1()
    put(g, 1, 2, ".")
    put(g, 4, 29, ".")
    put(g, 8, 1, ".")
    put(g, 6, 30, ".")
    put(g, 2, 4, "*")
    put(g, 3, 27, "*")
    put(g, 9, 0, "*")
    put(g, 7, 31, "*")
    return g


def frame_tired_1():
    g = grid(BASE)
    # 半目(上半分をまぶたに、瞳は下寄りのまま)
    for y in (2, 3):
        put(g, y, 8, "GGG")
        put(g, y, 21, "GGG")
    put(g, 3, 7, "KKKKK".replace("K", "K"))
    put(g, 3, 7, "GKKKG")
    put(g, 3, 20, "GKKKG")
    # 口を短いへの字に(牙は消す)
    replace_row(g, 10, 5, 26, "G")
    put(g, 11, 4, "GGGGGGGGGGGGGGGGGGGGGGGG")
    put(g, 10, 11, "KKKKKKKKKK")
    put(g, 11, 10, "K")
    put(g, 11, 21, "K")
    # 汗(左こめかみ)
    put(g, 6, 2, "Z")
    put(g, 8, 1, "Z")
    return g


def frame_tired_2():
    g = frame_tired_1()
    put(g, 6, 2, ".")
    put(g, 8, 1, ".")
    put(g, 7, 2, "Z")
    put(g, 9, 1, "Z")
    return g


def frame_sleep_1():
    g = _close_eyes(grid(BASE))
    # Zzz(左上)
    put(g, 0, 4, "Z")
    put(g, 2, 2, "ZZ")
    put(g, 5, 1, "Z")
    return g


def frame_sleep_2():
    g = _close_eyes(grid(BASE))
    put(g, 0, 2, "ZZ")
    put(g, 3, 1, "Z")
    put(g, 5, 3, "ZZ")
    return g


SPRITES = {
    "normal": [frame_normal_1, frame_normal_2, frame_normal_1, frame_blink],
    "happy": [frame_happy_1, frame_happy_2],
    "excellent": [frame_excellent_1, frame_excellent_2],
    "tired": [frame_tired_1, frame_tired_2],
    "sleeping": [frame_sleep_1, frame_sleep_2],
}

# ================================================================
# 敵モンスター・小物(アドベンチャーモード用)
# 各オブジェクトは {"w": 幅, "frames": [ASCIIグリッド, ...]}
# ================================================================

def _shift_down(rows, w):
    return ["." * w] + rows[:-1]


SLIME = [
    "",
    ".....KKKKKK",
    "....KmmmmmmK",
    "...KmmmmmmmmK",
    "..KmmmmmmmmmmK",
    ".KmWWmmmmmmWWmK",
    ".KmWPWmmmmWPWmK",
    ".KmWPWmmmmWPWmK",
    ".KmWWmmmmmmWWmK",
    "KmmmmmKKKKmmmmmK",
    "KmmmmmmmmmmmmmmK",
    "KmmmmmmmmmmmmmmK",
    ".KmmmmmmmmmmmmK",
    "..KKKKKKKKKKKK",
]

BAT_1 = [
    "",
    ".KK..........KK",
    ".KnnK......KnnK",
    "..KnnnKKKKnnnK",
    "..KnnnnnnnnnnK",
    ".KnnWWnnnnWWnnK",
    ".KnnWPnnnnWPnnK",
    ".KnnnnnnnnnnnnK",
    "..KnnKnnnnKnnK",
    "...KnWKnnKWnK",
    "....KKKKKKKK",
]

BAT_2 = [
    "",
    "",
    "",
    "...KKKKKKKKKK",
    "..KnnnnnnnnnnK",
    ".KnnWWnnnnWWnnK",
    "KKnnWPnnnnWPnnKK",
    "KnnKnnnnnnnnKnnK",
    "KnnKnKnnnnKnKnnK",
    ".KKKnWKnnKWnKKK",
    "....KKKKKKKK",
]

MUSHROOM = [
    "",
    ".....KKKKKK",
    "...KKeeeeeeKK",
    "..KeeWWeeeeeeK",
    ".KeeeWWeeeWWeeK",
    ".KeeeeeeeeWWeeK",
    ".KeeeeeeeeeeeeK",
    "..KKKKKKKKKKKK",
    "....KLLLLLLK",
    "....KLPLLPLK",
    "....KLLLLLLK",
    "....KLKKKKLK",
    "...KLLLLLLLLK",
    "....KKK..KKK",
]

GHOST = [
    "",
    ".....KKKKKK",
    "...KKssssssKK",
    "..KssssssssssK",
    ".KssPPssssPPssK",
    ".KssPPssssPPssK",
    ".KssssssssssssK",
    ".KsssKKKKKsssK",
    ".KssssssssssssK",
    ".KssssssssssssK",
    ".KssKssssssKssK",
    "..KK.KssssK.KK",
    "......KKKK",
]

GOLEM = [
    "..KKKKKKKKKKKK",
    ".KggggggggggggK",
    ".KgYYggggggYYgK",
    ".KgYYggggggYYgK",
    ".KggggggggggggK",
    ".KgggKKKKKKgggK",
    "..KKKKKKKKKKKK",
    "KKKggggggggKKKK",
    "KggKggggggKggKK",
    "KggKggggggKggK",
    "KKKKggggggKKKK",
    "...KggKKggK",
    "...KggK.KggK",
    "..KKggK.KggKK",
    "..KKKKK.KKKKK",
]

POT = [
    "",
    "....KKKKKK",
    "...KooooooK",
    "....KKKKKK",
    "...KooooooK",
    "..KooooooooK",
    ".KoooooooodoK",
    ".KoooooooodoK",
    ".KoooooooodoK",
    "..KooooooooK",
    "...KKKKKKKK",
]

POT_BROKEN = [
    "",
    "",
    "",
    "",
    "",
    "..K..KK...K",
    ".KoK.KooK.KoK",
    ".KooKoooooKoK",
    ".KoooooodooK",
    "..KooooooooK",
    "...KKKKKKKK",
]

HERB = [
    "",
    ".KK..KK",
    "KGGKKGGK",
    "KGGGGGGK",
    ".KGGGGK",
    "..KDDK",
    "..KDDK",
]

COIN = [
    ".KKKK",
    "KYYYYK",
    "KYWYYK",
    "KYYYYK",
    ".KKKK",
]

# カレンダー予定の割り込み敵「じかんまじん」(目覚まし時計)
CLOCK = [
    "",
    "..KK........KK",
    ".KYYK......KYYK",
    "..KKKKKKKKKKKK",
    "...KYYYYYYYYK",
    "..KYWWWWWWWWYK",
    ".KYWWWWPWWWWWYK",
    ".KYWWWWPWWWWWYK",
    ".KYWWWWPPPWWWYK",
    ".KYWWWWWWWWWWYK",
    "..KYWWWWWWWWYK",
    "...KYYYYYYYYK",
    "....KKKKKKKK",
    "...KKK....KKK",
]

OBJECTS = {
    "slime": {"w": 16, "frames": [SLIME, _shift_down(SLIME, 16)]},
    "bat": {"w": 16, "frames": [BAT_1, BAT_2]},
    "mushroom": {"w": 16, "frames": [MUSHROOM, _shift_down(MUSHROOM, 16)]},
    "ghost": {"w": 16, "frames": [GHOST, _shift_down(GHOST, 16)]},
    "golem": {"w": 16, "frames": [GOLEM, _shift_down(GOLEM, 16)]},
    "pot": {"w": 14, "frames": [POT]},
    "pot_broken": {"w": 14, "frames": [POT_BROKEN]},
    "herb": {"w": 8, "frames": [HERB]},
    "coin": {"w": 6, "frames": [COIN]},
    "clock": {"w": 16, "frames": [CLOCK, _shift_down(CLOCK, 16)]},
}


# ---- PNG書き出し(純Python) ----

def write_png(path: Path, pixels, scale=1, bg=None):
    """pixels: HxWの(r,g,b)|Noneの2次元配列"""
    h = len(pixels)
    w = len(pixels[0])
    raw = b""
    for y in range(h):
        row = b"\x00"
        for x in range(w):
            px = pixels[y][x]
            if px is None:
                px = bg
            rgba = (px + (255,)) if px else (0, 0, 0, 0)
            row += struct.pack("4B", *rgba) * scale
        raw += row * scale

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", w * scale, h * scale, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


def render(rows):
    return [[PALETTE.get(ch) for ch in row] for row in rows]


def main():
    base_dir = Path(__file__).resolve().parent.parent
    static_dir = base_dir / "static"
    static_dir.mkdir(exist_ok=True)

    data = {}
    for name, frames in SPRITES.items():
        data[name] = [to_rows(f()) for f in frames]

    objects_js = {}
    for name, obj in OBJECTS.items():
        frames = [to_rows(grid(f, obj["w"])) for f in obj["frames"]]
        objects_js[name] = {"w": obj["w"], "h": len(frames[0]), "frames": frames}

    palette_js = {k: (f"rgb({v[0]},{v[1]},{v[2]})" if v else None) for k, v in PALETTE.items()}
    js = (
        "// gen_sprites.pyから自動生成。直接編集しないこと。\n"
        f"export const PALETTE = {json.dumps(palette_js, ensure_ascii=False)};\n"
        f"export const SPRITES = {json.dumps(data, ensure_ascii=False)};\n"
        f"export const OBJECTS = {json.dumps(objects_js, ensure_ascii=False)};\n"
        f"export const SPRITE_W = {W};\nexport const SPRITE_H = {H};\n"
    )
    (static_dir / "sprites.js").write_text(js, encoding="utf-8")
    print(f"wrote {static_dir / 'sprites.js'}")

    # アイコン: happyフレームを背景色付きで
    icon_px = render(to_rows(frame_happy_1()))
    write_png(static_dir / "icon-192.png", icon_px, scale=6, bg=(232, 244, 221))
    write_png(static_dir / "icon-512.png", icon_px, scale=16, bg=(232, 244, 221))
    print("wrote icons")

    if "--preview" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--preview") + 1])
        out.mkdir(parents=True, exist_ok=True)
        for name, frames in SPRITES.items():
            for i, f in enumerate(frames):
                write_png(out / f"{name}_{i}.png", render(to_rows(f())), scale=10)
        for name, obj in OBJECTS.items():
            for i, f in enumerate(obj["frames"]):
                write_png(out / f"obj_{name}_{i}.png",
                          render(to_rows(grid(f, obj["w"]))), scale=10)
        print(f"wrote previews to {out}")


if __name__ == "__main__":
    main()
