use image;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
//
// Takes the bytes of an image, then generates a hash from their pixels
// But since it's in Rust it does it super speedy fast
#[pyfunction]
fn generate_hash(buffer: &[u8]) -> PyResult<usize> {
    let image_original = match image::load_from_memory(buffer) {
        Ok(val) => val,
        Err(_err) => return Ok(0),
    }; // Avoid panicking in unrecognized formats

    // Resize to 8x8px, ignore aspect ratio
    let img = image_original.resize_exact(8, 8, image::imageops::Lanczos3);
    let img = img.to_luma8();

    let mut pixels: Vec<u8> = Vec::new();

    // Need to create a vector of pixels so it can be indexed
    for pixel in img.pixels() {
        pixels.push(pixel[0]);
    }

    let mut prev_px = pixels[0];
    let mut diff_hash = 0;

    for pixel in pixels {
        diff_hash <<= 1; // Shift the hash left once each pixel
        diff_hash |= (pixel >= prev_px) as usize;
        prev_px = pixel;
    }

    Ok((diff_hash))
}

#[pymodule]
fn image_hash(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_hash, m)?)?;

    Ok(())
}
