"""
ドット絵ワニ博士のスプライト生成スクリプト(単一ソース)。

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
    ".": None,           # 透明
    "K": (20, 61, 32),    # 輪郭(濃緑)
    "G": (63, 163, 77),   # 体(緑)
    "D": (45, 122, 58),   # 体の影
    "L": (205, 237, 181), # 腹・口まわり(薄緑)
    "B": (38, 38, 46),    # 角帽(黒)
    "S": (72, 72, 88),    # 角帽ハイライト
    "Y": (255, 212, 71),  # 房(タッセル)
    "W": (255, 255, 255), # 目・歯
    "P": (28, 28, 28),    # 瞳
    "R": (224, 82, 106),  # 口の中
    "C": (255, 158, 158), # ほっぺ
    "Z": (122, 162, 247), # Zzz
    "*": (255, 220, 120), # キラキラ
}

W = 32
H = 32

# ---- ベース(ふつう・フレーム1) ----
# 32x32。行は上から。grid()が右側を透明で埋めるので末尾のドットは省略可。
BASE = [
    "",
    "...............BB",
    ".....BBBBBBBBBBBBBBBBBBBBBB",
    "...BBBBBBBBBBBBBBBBBBBBBBBBBB",
    "..........BBBBBBBBBBBB.....Y",
    "..........BBBBBBBBBBBB.....Y",
    "........KGGGGGGGGGGGGK....YY",
    ".......KGGGGGGGGGGGGGGK",
    "......KGGWWWWGGGGWWWWGGK",
    "......KGWWWWWWGGWWWWWWGK",
    "......KGWWPPWWGGWWPPWWGK",
    "......KGWWPPWWGGWWPPWWGK",
    "......KGGWWWWGGGGWWWWGGK",
    "......KGGGGGGGGGGGGGGGGK",
    ".....KGGLLDDLLLLLLDDLLGGK",
    ".....KGLLLLLLLLLLLLLLLLGK",
    ".....KGLKKKKKKKKKKKKKKLGK",
    ".....KGLLWWLLLLLLLLWWLLGK",
    ".....KGGLLLLLLLLLLLLLLGGK",
    "......KGGGGGGGGGGGGGGGGK",
    ".......KGGGGGGGGGGGGGGK",
    "......KGGGGLLLLLLLLGGGGK",
    ".....KGGGGGLLLLLLLLGGGGGK",
    ".....KGGKGGLLLLLLLLGGKGGK",
    ".....KGGKGGLLLLLLLLGGKGGK",
    "......KK.KGGLLLLLLGGK.KK",
    ".........KGGGGGGGGGGK",
    ".........KGGGGGGGGGGK",
    ".........KGGK....KGGK",
    ".........KGGK....KGGK",
    "........KKGGKK..KKGGKK",
    "........KKKKKK..KKKKKK",
]


def grid(rows):
    # 行長のタイプミスを許容: 32桁に満たなければ透明で右詰め、超えたらエラー
    fixed = []
    for i, r in enumerate(rows):
        if len(r) > W:
            raise ValueError(f"row {i} is {len(r)} chars (max {W}): {r}")
        fixed.append(list(r.ljust(W, ".")))
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


# ---- バリアント生成 ----

def frame_normal_1():
    return grid(BASE)


def frame_normal_2():
    """呼吸: 全体を1px下げる(帽子含む)。"""
    g = grid(BASE)
    return [list("." * W)] + g[:-1]


def frame_blink():
    g = grid(BASE)
    # 目を閉じる(白目を体色に、瞳をまぶた線に)
    for y in (8, 9, 10, 11, 12):
        put(g, y, 8, "GGGGGG")
        put(g, y, 16, "GGGGGG")
    put(g, 11, 9, "KKKK")
    put(g, 11, 17, "KKKK")
    return g


def frame_happy_1():
    g = grid(BASE)
    # 口: 開いた笑顔(中は赤、両端に白い牙)
    replace_row(g, 16, 8, 21, "L")
    replace_row(g, 17, 9, 20, "L")
    put(g, 16, 9, "KWWKRRRRRRKWWK")
    put(g, 17, 10, "KRRRRRRRRRRK")
    put(g, 18, 11, "KKKKKKKKKK")
    # ほっぺ
    put(g, 13, 8, "CC")
    put(g, 13, 20, "CC")
    return g


def frame_happy_2():
    g = frame_happy_1()
    return [list("." * W)] + g[:-1]


def frame_excellent_1():
    g = frame_happy_1()
    # 側面の腕を消して(体の輪郭に戻して)バンザイの腕を描く
    put(g, 23, 5, "KGGGG")
    put(g, 23, 20, "GGGGK")
    put(g, 24, 5, "KGGGG")
    put(g, 24, 20, "GGGGK")
    put(g, 25, 6, "KGG")
    put(g, 25, 20, "GKK")
    # 頭の横に上げた腕(こぶし付き)
    put(g, 15, 2, "KK")
    put(g, 16, 1, "KGGK")
    put(g, 17, 1, "KGGK")
    put(g, 18, 2, "KGK")
    put(g, 19, 3, "KGK")
    put(g, 20, 4, "KGK")
    put(g, 15, 28, "KK")
    put(g, 16, 27, "KGGK")
    put(g, 17, 27, "KGGK")
    put(g, 18, 27, "KGK")
    put(g, 19, 26, "KGK")
    put(g, 20, 25, "KGK")
    # キラキラ
    put(g, 1, 3, "*")
    put(g, 5, 30, "*")
    put(g, 11, 2, "*")
    put(g, 9, 29, "*")
    return g


def frame_excellent_2():
    g = frame_excellent_1()
    # キラキラの位置を変える
    put(g, 1, 3, ".")
    put(g, 5, 30, ".")
    put(g, 11, 2, ".")
    put(g, 9, 29, ".")
    put(g, 3, 1, "*")
    put(g, 8, 31, "*")
    put(g, 13, 1, "*")
    put(g, 2, 29, "*")
    return g


def frame_tired_1():
    g = grid(BASE)
    # 半目(白目の上半分をまぶたに)
    for y in (8, 9):
        put(g, y, 8, "GGGGGG")
        put(g, y, 16, "GGGGGG")
    put(g, 10, 9, "KKKK")
    put(g, 10, 17, "KKKK")
    # 口をへの字(∩)に、牙は消す
    replace_row(g, 16, 8, 21, "L")
    replace_row(g, 17, 9, 20, "L")
    put(g, 15, 11, "K")
    put(g, 15, 18, "K")
    put(g, 16, 12, "KKKKKK")
    # 汗(左こめかみ)
    put(g, 8, 3, "Z")
    put(g, 10, 2, "Z")
    return g


def frame_tired_2():
    g = frame_tired_1()
    put(g, 8, 3, ".")
    put(g, 10, 2, ".")
    put(g, 9, 3, "Z")
    put(g, 11, 2, "Z")
    return g


def frame_sleep_1():
    g = frame_blink()
    # Zzz(左上、帽子と重ならない位置)
    put(g, 1, 4, "Z")
    put(g, 3, 2, "ZZ")
    put(g, 6, 1, "Z")
    return g


def frame_sleep_2():
    g = frame_blink()
    put(g, 0, 3, "ZZ")
    put(g, 2, 1, "Z")
    put(g, 5, 0, "ZZ")
    return g


SPRITES = {
    "normal": [frame_normal_1, frame_normal_2, frame_normal_1, frame_blink],
    "happy": [frame_happy_1, frame_happy_2],
    "excellent": [frame_excellent_1, frame_excellent_2],
    "tired": [frame_tired_1, frame_tired_2],
    "sleeping": [frame_sleep_1, frame_sleep_2],
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

    palette_js = {k: (f"rgb({v[0]},{v[1]},{v[2]})" if v else None) for k, v in PALETTE.items()}
    js = (
        "// gen_sprites.pyから自動生成。直接編集しないこと。\n"
        f"export const PALETTE = {json.dumps(palette_js, ensure_ascii=False)};\n"
        f"export const SPRITES = {json.dumps(data, ensure_ascii=False)};\n"
        f"export const SPRITE_W = {W};\nexport const SPRITE_H = {H};\n"
    )
    (static_dir / "sprites.js").write_text(js, encoding="utf-8")
    print(f"wrote {static_dir / 'sprites.js'}")

    # アイコン: happyフレームを背景色付きで
    icon_px = render(to_rows(frame_happy_1()))
    write_png(static_dir / "icon-192.png", icon_px, scale=6, bg=(240, 249, 235))
    write_png(static_dir / "icon-512.png", icon_px, scale=16, bg=(240, 249, 235))
    print("wrote icons")

    if "--preview" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--preview") + 1])
        out.mkdir(parents=True, exist_ok=True)
        for name, frames in SPRITES.items():
            for i, f in enumerate(frames):
                write_png(out / f"{name}_{i}.png", render(to_rows(f())), scale=10)
        print(f"wrote previews to {out}")


if __name__ == "__main__":
    main()
