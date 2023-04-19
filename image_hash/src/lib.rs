use pyo3::{prelude::*, wrap_pyfunction};

/// Compare two hashes and return a percent similarity
#[pyfunction]
fn compare_hashes(hash1: &str, hash2: &str) -> PyResult<u8> {
    // hash1 and hash2 are accepted as &str because it results in the
    // lowest amount of Python conversion operations
    let hash1 = hash1.parse::<usize>()?;
    let hash2 = hash2.parse::<usize>()?;

    let hash_xor = format!("{:#b}", (hash1 ^ hash2));
    let occurences: f64 = hash_xor.match_indices('1').count() as f64;
    let result = (((64.0 - occurences) * 100.0) / 64.0) as u8;

    Ok(result)
}

/// Generates a hash of an image
///
/// Takes a bytes buffer and returns a `usize` difference hash of an image.
/// Returns `0` if the image coult not be opened.
#[pyfunction]
fn generate_hash(buffer: &[u8]) -> PyResult<usize> {
    // Avoid panicking in unrecognized formats, return 0 for easy of ignoring
    let image_original = match image::load_from_memory(buffer) {
        Ok(val) => val,
        Err(_err) => return Ok(0),
    };

    // Resize to 8x8px, ignore aspect ratio, convert to greyscale
    let img = image_original
        .resize_exact(8, 8, image::imageops::Lanczos3)
        .to_luma8();

    // Get the image pixels, map them to their inner value, collect to a Vec
    let mut pixels: Vec<u8> = img.pixels().map(|px| px[0]).collect();

    // Mutably chunk pixels Vec, then for every other element
    // (starting at index 1) reverse the chunk
    for row in pixels.chunks_mut(8).skip(1).step_by(2) {
        row.reverse();
    }

    let mut prev_px = img.get_pixel(0, 7)[0];
    let mut diff_hash = 0;

    for pixel in pixels {
        diff_hash <<= 1;
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
