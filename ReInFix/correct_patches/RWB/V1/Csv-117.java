public String get(final Enum<?> e) {
    if (e == null) {
        throw new IllegalArgumentException("Enum e cannot be null.");
    }
    return get(e.name());
}