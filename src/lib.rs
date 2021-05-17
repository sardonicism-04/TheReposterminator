use image;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

// Takes the bytes of an image, then generates a hash from their pixels
// But since it's in Rust it does it super speedy fast
#[pyfunction]
fn generate_hash(buffer: &[u8]) -> PyResult<usize> {
    let image_original = image::load_from_memory(buffer).unwrap();
    let img = image_original.resize(8, 8, image::imageops::Lanczos3);
    let img = img.to_luma8();

    let mut pixels: Vec<u8> = Vec::new();

    for pixel in img.pixels() {
        pixels.push(pixel[0]);
    }

    let mut prev_px = pixels[0];
    let mut diff_hash = 0;

    for pixel in pixels {
        diff_hash <<= 1;
        diff_hash |= ((pixel >= prev_px) as usize);
        prev_px = pixel;
    }

    Ok((diff_hash))
}

#[pymodule]
fn image_hash(py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_hash, m)?)?;

    Ok(())
}
