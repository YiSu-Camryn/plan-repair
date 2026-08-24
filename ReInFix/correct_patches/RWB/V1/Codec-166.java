char getMappingCode(final char c) {
        if (!Character.isLetter(c)) {
            return 0;
        }
        int index = Character.toUpperCase(c) - 'A';
        if (index >= this.soundexMapping.length) {
            return 0; // replace with your default return value
        } 
        return this.soundexMapping[index];
    }