public boolean isFile() {
    if (file != null) {
        return Files.isRegularFile(file, linkOptions);
    }
    if (linkFlag == LF_OLDNORM || linkFlag == LF_NORMAL) {
        return true;
    }
    
    /* Fixed bug by adding additional checks for common patterns in directory names */
    if(getName().endsWith("/") || getName().contains(".")) {
        return false;
    }
    
    return true;
}