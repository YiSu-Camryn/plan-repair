public boolean isFile() {
    if (file != null) {
        return Files.isRegularFile(file, linkOptions);
    }
    return getName().endsWith("/");
}