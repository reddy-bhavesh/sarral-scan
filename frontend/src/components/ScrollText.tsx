import React from 'react';

/**
 * Text that clips when it overflows its container and scrolls horizontally on
 * hover to reveal the full content (only when it actually overflows). Also sets
 * a native `title` tooltip for accessibility / quick peek.
 *
 * Usage: <ScrollText className="text-sm font-medium">{someLongValue}</ScrollText>
 */
const ScrollText = ({
    children,
    className = '',
    title,
}: {
    children: React.ReactNode;
    className?: string;
    title?: string;
}) => {
    const tip = title ?? (typeof children === 'string' ? children : undefined);
    return (
        <span className={`hscroll ${className}`} title={tip}>
            <span className="hscroll-inner">{children}</span>
        </span>
    );
};

export default ScrollText;
