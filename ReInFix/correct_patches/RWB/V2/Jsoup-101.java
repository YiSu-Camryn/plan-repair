private boolean isInlineable(Document.OutputSettings out) {
    // Special handling for <br> elements which should always be printed on a new line.
    if (tag.getName().equals("br")) {
        return false;
    }
    if (!tag.isInline()) {
        return false;
    }
    return (parent() == null || parent().isBlock())
        && !isEffectivelyFirst()
        && !out.outline();
}