char getMappingCode(final char c) {
    if (!Character.isLetter(c)) {
        return 0;
    }
    int index = Character.toUpperCase(c) - 'A';
    if (index >= 0 && index < this.soundexMapping.length) {
        return this.soundexMapping[index];
    } else {
        return 0; // Or throw an exception, depending on desired behavior
    }
}