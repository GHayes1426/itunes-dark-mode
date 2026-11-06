"""Translate the verified drawing sites for the 12.13.12.3 executable."""
NEW_BUILD = "2370b094ec723529907ae133b291fa4df97f6e95c13f4dd600b78283a1ed1d52"
OLD_BUILD = "c69e719cd3f2f9374e71c954a6de87002b6988af65129943983a2f17490dd73c"

def adapt_source(source, digest):
    if digest == OLD_BUILD:
        return source
    if digest != NEW_BUILD:
        raise RuntimeError("Unverified iTunes executable")
    replacements = {
        "0xb3a196": "0x1443446",
        "0xb3c42e": "0x1445740",
        "0xb391ba": "0x1441dac",
        "0xb39084": "0x1441c47",
        "0xb366d3": "0x143f859",
        "0x29d717": "0xed01ac",
        "0xd81888": "0xd8da89",
    }
    for old, new in replacements.items():
        source = source.replace(old, new)
    source = source.replace("this.context.rdi.add(i*8).readDouble()", "this.context.r14.add(i*8).readDouble()")
    source = source.replace("this.returnAddress.equals(exe.base.add(0xc34e14))",
        "[0x1446f32,0x144711a].some(rva=>this.returnAddress.equals(exe.base.add(rva)))")
    return source

