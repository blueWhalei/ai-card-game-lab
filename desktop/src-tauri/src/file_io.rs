//! Complete a file before replacing its destination. No frontend path capability.
use std::{io::Write, path::Path};

pub fn replace_file(path: &Path, bytes: &[u8]) -> std::io::Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| std::io::Error::other("Missing parent directory"))?;
    let mut temporary = tempfile::NamedTempFile::new_in(parent)?;
    temporary.write_all(bytes)?;
    temporary.as_file().sync_all()?;
    temporary.persist(path).map_err(|error| error.error)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn creates_and_replaces_a_complete_file_without_leaving_temporary_files() {
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("研究 report.json");
        replace_file(&path, b"first").unwrap();
        replace_file(&path, b"second").unwrap();
        assert_eq!(fs::read(&path).unwrap(), b"second");
        assert_eq!(fs::read_dir(root.path()).unwrap().count(), 1);
    }

    #[test]
    fn failed_replacement_keeps_existing_destination_and_cleans_up_temporary_file() {
        let root = tempfile::tempdir().unwrap();
        let destination = root.path().join("directory.json");
        fs::create_dir(&destination).unwrap();
        fs::write(destination.join("kept"), b"untouched").unwrap();
        assert!(replace_file(&destination, b"new content").is_err());
        assert_eq!(fs::read(destination.join("kept")).unwrap(), b"untouched");
        assert_eq!(fs::read_dir(root.path()).unwrap().count(), 1);
    }
}
