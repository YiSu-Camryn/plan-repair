private static String getMantissa(final String str, final int stopPos) {
    final char firstChar = str.charAt(0);
    final boolean hasSign = firstChar == '-' || firstChar == '+';
    int adjustedStopPos = hasSign ? stopPos - 1 : stopPos; // Adjust stopPos based on sign
    if (adjustedStopPos < 0) {
        adjustedStopPos = 0; // Ensure adjustedStopPos is not negative
    }
    return hasSign ? str.substring(1, adjustedStopPos + 1) : str.substring(0, adjustedStopPos);
}