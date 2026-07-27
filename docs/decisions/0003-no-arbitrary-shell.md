# Decision 0003: no arbitrary shell passthrough

Status: accepted in starter

Contract version 1 supports only exact repository-relative entry points and typed flag parameters.
There is no command string, shell runner, positional passthrough, or model-provided path.

Convenience does not justify turning the operator plane into an unbounded executor.
