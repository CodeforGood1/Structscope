struct RustPoint {
    x: i32,
    y: i32,
}

struct RustMixed {
    tag: u8,
    value: f64,
    state: u8,
}

pub struct RustPointers {
    ptr: usize,
    len: u32,
    flag: bool,
}

