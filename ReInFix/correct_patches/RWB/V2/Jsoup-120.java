private String consumeSubQuery() {
    StringBuilder sq = StringUtil.borrowBuilder();
    boolean seenNonCombinator = false;
    while (!tq.isEmpty()) {
        if (tq.matches("(")) {
            sq.append("(").append(tq.chompBalanced('(', ')')).append(")");
            seenNonCombinator = true;
        } else if (tq.matches("[")) {
            sq.append("[").append(tq.chompBalanced('[', ']')).append("]");
            seenNonCombinator = true;
        } else if (tq.matchesAny(Combinators)) {
            if (seenNonCombinator)
                break;
            else
                sq.append(tq.consume());
        } else {
            seenNonCombinator = true;
            sq.append(tq.consume());
        }
    }
    return StringUtil.releaseBuilder(sq);
}