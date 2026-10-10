# Native Apple platforms

Use platform-native frameworks and controls when feasible. Respect current Apple HIG and API availability for the deployment target.

## iOS / iPadOS
- SwiftUI/UIKit controls should adapt to Dynamic Type, system appearance, safe areas, VoiceOver and device size.
- Favor familiar navigation hierarchy; only use tab navigation for genuinely peer destinations.
- Consider one-handed reach, touch targets, permission timing, sheet and modal dismissal.
- iPad interfaces should adapt to wide screens and multitasking, not simply stretch iPhone layouts.

## macOS
- Design for resizable windows, mouse/trackpad, keyboard shortcuts, context menus, focus, selection and multiwindow behavior.
- Use native menu/toolbar/sidebar patterns where appropriate; don't force mobile bottom tabs onto desktop.
- Honor accessibility, system colors, reduced motion, font sizing, and platform conventions.

## Platforms are not interchangeable
- Share information architecture and brand where useful, but choose appropriate components and interactions per platform.
- System fonts, colors, native materials and SF Symbols should be used through Apple's supported platform tooling and under applicable licenses.

Official guides: https://developer.apple.com/design/human-interface-guidelines/designing-for-ios ; https://developer.apple.com/design/human-interface-guidelines/designing-for-macos
