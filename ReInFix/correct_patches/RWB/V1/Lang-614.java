private static String getMantissa(final String str, final int stopPos) {
        try {
            final char firstChar = str.charAt(0); 
            final boolean hasSign = firstChar == '-' || firstChar == '+'; 
            return hasSign ? str.substring(1, stopPos) : str.substring(0, stopPos); 
        } catch (IndexOutOfBoundsException e) {
            return ""; 
        }
    }