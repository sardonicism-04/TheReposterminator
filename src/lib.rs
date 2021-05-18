use image;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

// Compare two hashes and return a percent similarity
#[pyfunction]
fn compare_hashes(hash1: &str, hash2: &str) -> PyResult<usize> {
    let hash1 = hash1.parse::<usize>()?;
    let hash2 = hash2.parse::<usize>()?;

    let hash_xor = format!("{:#b}", (hash1 ^ hash2));
    let occurences: usize = hash_xor.match_indices("1").collect::<Vec<_>>().len();
    let result = (((64.0 - occurences as f64) * 100.0) / 64.0) as usize;

    Ok(result)
}

// Takes the bytes of an image, then generates a hash from their pixels
// But since it's in Rust it does it super speedy fast
#[pyfunction]
fn generate_hash(buffer: &[u8]) -> PyResult<usize> {
    let image_format = match image::guess_format(buffer) {
        Ok(val) => val,
        Err(_err) => return Ok(0),
    };
    // Avoid panicking in unrecognized formats

    let image_original = image::load_from_memory_with_format(buffer, image_format).unwrap();

    // Resize to 8x8px, ignore aspect ratio
    let img = image_original.resize_exact(8, 8, image::imageops::Lanczos3);
    let img = img.to_luma8();

    // Need to create a vector of pixels so it can be indexed
    let all_pixels: Vec<u8> = img.pixels().cloned().map(|px| px[0]).collect();
    let mut all_pixels_chunked: Vec<Vec<u8>> =
        all_pixels.chunks(8).map(|chunk| chunk.to_vec()).collect();

    for i in (1..8).step_by(2) {
        let mut to_flip = all_pixels_chunked.remove(i);
        to_flip.reverse();
        all_pixels_chunked.insert(i, to_flip);
    }

    let pixels: Vec<u8> = all_pixels_chunked.concat();

    let mut prev_px = img.get_pixel(0, 7)[0];
    let mut diff_hash = 0;

    for pixel in pixels {
        diff_hash <<= 1; // Shift the hash left once each pixel
        diff_hash |= (pixel >= prev_px) as usize;
        prev_px = pixel;
    }

    Ok(diff_hash)
}

#[pymodule]
fn image_hash(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(generate_hash, m)?)?;
    m.add_function(wrap_pyfunction!(compare_hashes, m)?)?;

    Ok(())
}
