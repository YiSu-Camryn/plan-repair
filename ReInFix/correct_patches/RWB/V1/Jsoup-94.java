protected void replaceChild(Node out, Node in) {
    Validate.isTrue(out.parentNode == this);
    Validate.notNull(in);
    if (in == out){ 
        return; // the 'in' node and 'out' node are identical, no need for replacement
    }
    if (in.parentNode != null)
        in.parentNode.removeChild(in);
    final int index = out.siblingIndex;
    ensureChildNodes().set(index, in);
    in.parentNode = this;
    in.setSiblingIndex(index);
    out.parentNode = null;
}