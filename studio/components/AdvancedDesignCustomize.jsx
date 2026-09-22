'use client'

import { useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Search, Sparkles } from 'lucide-react'

const YES_NO_AUTO = ['On', 'Off']
const COMPACTNESS = ['Ultra Compact', 'Compact', 'Comfortable', 'Spacious']

const SECTIONS = [
  {
    key: 'layout', title: 'Layout & Page Structure',
    controls: [
      ['pageLayout', 'Page layout', 'select', ['Boxed', 'Full Width', 'Split', 'Centered', 'Dashboard']],
      ['maxWidth', 'Max content width', 'select', ['960px', '1200px', '1440px', '1600px', 'Fluid']],
      ['pagePadding', 'Page padding', 'select', ['Compact', 'Normal', 'Spacious', 'Custom']],
      ['sectionGap', 'Section gap', 'select', ['Tight', 'Normal', 'Large', 'Custom']],
      ['gridColumns', 'Grid columns', 'select', ['1', '2', '3', '4', '6', '12']],
      ['sidebarWidth', 'Sidebar width', 'select', ['Compact', 'Normal', 'Wide', 'Custom']],
      ['headerHeight', 'Header height', 'select', ['Compact', 'Normal', 'Tall', 'Custom']],
      ['stickyHeader', 'Sticky header', 'select', YES_NO_AUTO],
      ['stickySidebar', 'Sticky sidebar', 'select', YES_NO_AUTO],
      ['footerStyle', 'Footer style', 'select', ['Simple', 'Multi-column', 'Minimal', 'Hidden']],
    ],
  },
  {
    key: 'responsive', title: 'Responsive Design',
    controls: [
      ['deviceStrategy', 'Responsive strategy', 'select', ['Mobile First', 'Desktop First', 'Balanced']],
      ['mobileNavigation', 'Mobile navigation', 'select', ['Bottom Nav', 'Drawer', 'Hamburger', 'Tabs']],
      ['tabletLayout', 'Tablet layout', 'select', ['Stacked', 'Two Column', 'Desktop-like', 'Custom']],
      ['mobileCardLayout', 'Mobile card layout', 'select', ['Single Column', 'Horizontal', 'Carousel', 'Compact']],
      ['mobileTableMode', 'Mobile table mode', 'select', ['Scroll', 'Cards', 'Collapse']],
      ['breakpoints', 'Breakpoint profile', 'select', ['Standard', 'Tailwind', 'Bootstrap', 'Custom']],
      ['responsiveFonts', 'Responsive font scaling', 'select', YES_NO_AUTO],
      ['responsiveSpacing', 'Responsive spacing scaling', 'select', YES_NO_AUTO],
      ['deviceVisibility', 'Per-device visibility', 'select', ['Allowed', 'Avoid', 'Only when necessary']],
    ],
  },
  {
    key: 'navbar', title: 'Header / Navbar',
    controls: [
      ['style', 'Navbar style', 'select', ['Minimal', 'Floating', 'Glass', 'Full Width', 'Centered']],
      ['logoPosition', 'Logo position', 'select', ['Left', 'Center', 'Right']],
      ['alignment', 'Navigation alignment', 'select', ['Left', 'Center', 'Right', 'Split']],
      ['searchPosition', 'Search position', 'select', ['Hidden', 'Inline', 'Center', 'Right', 'Command']],
      ['cta', 'CTA button', 'select', ['Visible', 'Hidden', 'Contextual']],
      ['profileMenu', 'Profile menu', 'select', ['Avatar', 'Avatar + Name', 'Dropdown', 'Compact']],
      ['notificationStyle', 'Notification icon', 'select', ['Outline', 'Filled', 'Badge', 'Dot']],
      ['border', 'Navbar border', 'select', ['None', 'Hairline', 'Strong']],
      ['shadow', 'Navbar shadow', 'select', ['None', 'Soft', 'Elevated']],
      ['transparentTop', 'Transparent on top', 'select', YES_NO_AUTO],
    ],
  },
  {
    key: 'sidebar', title: 'Sidebar',
    controls: [
      ['width', 'Sidebar size', 'select', ['Compact', 'Normal', 'Wide']],
      ['content', 'Sidebar content', 'select', ['Icon only', 'Icon + text']],
      ['attachment', 'Placement', 'select', ['Floating', 'Attached']],
      ['collapsible', 'Collapsible', 'select', YES_NO_AUTO],
      ['dividers', 'Section dividers', 'select', ['None', 'Subtle', 'Strong']],
      ['activeStyle', 'Active item style', 'select', ['Background', 'Left border', 'Pill', 'Underline']],
      ['iconSize', 'Icon size', 'select', ['Small', 'Medium', 'Large']],
      ['nestedStyle', 'Nested navigation', 'select', ['Indent', 'Accordion', 'Tree', 'Flyout']],
      ['footerStyle', 'Sidebar footer/profile', 'select', ['Minimal', 'Profile card', 'Actions', 'Hidden']],
    ],
  },
  {
    key: 'cards', title: 'Cards',
    controls: [
      ['style', 'Card style', 'select', ['Flat', 'Elevated', 'Outline', 'Soft', 'Glass', 'Borderless']],
      ['radius', 'Card radius', 'select', ['Sharp', 'Slight', 'Rounded', 'Large', 'Pill-like']],
      ['padding', 'Card padding', 'select', COMPACTNESS],
      ['shadow', 'Card shadow', 'select', ['None', 'Soft', 'Medium', 'Dramatic']],
      ['border', 'Card border', 'select', ['None', 'Hairline', 'Strong']],
      ['hover', 'Hover animation', 'select', ['None', 'Lift', 'Glow', 'Scale', 'Border']],
      ['imagePosition', 'Image position', 'select', ['Top', 'Left', 'Right', 'Background', 'Hidden']],
      ['separation', 'Header/footer separation', 'select', ['None', 'Divider', 'Surface']],
      ['density', 'Card density', 'select', COMPACTNESS],
      ['interactive', 'Interactive card style', 'select', ['Subtle', 'Clickable', 'Selectable', 'Draggable']],
    ],
  },
  {
    key: 'buttons', title: 'Buttons',
    controls: [
      ['height', 'Button height', 'select', ['Compact', 'Normal', 'Large']],
      ['radius', 'Button radius', 'select', ['Sharp', 'Slight', 'Rounded', 'Pill']],
      ['weight', 'Font weight', 'select', ['400', '500', '600', '700']],
      ['iconPosition', 'Icon position', 'select', ['Left', 'Right', 'Icon-only', 'Contextual']],
      ['primary', 'Primary style', 'select', ['Solid', 'Gradient', 'Soft', 'Elevated']],
      ['secondary', 'Secondary style', 'select', ['Solid', 'Soft', 'Outline', 'Ghost']],
      ['outline', 'Outline style', 'select', ['Thin', 'Medium', 'Bold']],
      ['ghost', 'Ghost style', 'select', ['Plain', 'Tinted', 'Underline']],
      ['danger', 'Danger style', 'select', ['Solid', 'Soft', 'Outline']],
      ['hover', 'Hover effect', 'select', ['None', 'Lighten', 'Darken', 'Lift', 'Glow']],
      ['press', 'Press effect', 'select', ['None', 'Scale', 'Inset', 'Ripple']],
      ['loading', 'Loading state', 'select', ['Spinner', 'Dots', 'Progress', 'Text']],
      ['disabled', 'Disabled state', 'select', ['Fade', 'Muted', 'Outline']],
      ['mobileFullWidth', 'Full-width on mobile', 'select', YES_NO_AUTO],
    ],
  },
  {
    key: 'forms', title: 'Forms',
    controls: [
      ['inputStyle', 'Input style', 'select', ['Outline', 'Filled', 'Underline', 'Soft']],
      ['inputHeight', 'Input height', 'select', ['Compact', 'Normal', 'Large']],
      ['inputRadius', 'Input radius', 'select', ['Sharp', 'Slight', 'Rounded', 'Pill']],
      ['labelPosition', 'Label position', 'select', ['Top', 'Floating', 'Inside']],
      ['density', 'Form density', 'select', COMPACTNESS],
      ['focus', 'Focus style', 'select', ['Ring', 'Border', 'Glow', 'Underline']],
      ['error', 'Error style', 'select', ['Inline', 'Below', 'Toast', 'Summary']],
      ['success', 'Success style', 'select', ['Inline', 'Icon', 'Border', 'Toast']],
      ['helper', 'Helper text', 'select', ['Always', 'On focus', 'Contextual', 'Hidden']],
      ['checkbox', 'Checkbox style', 'select', ['Square', 'Rounded', 'Custom']],
      ['radio', 'Radio style', 'select', ['Circle', 'Card', 'Button']],
      ['toggle', 'Toggle style', 'select', ['Switch', 'Segmented', 'Button']],
      ['select', 'Select/dropdown', 'select', ['Native-like', 'Floating', 'Searchable', 'Command']],
      ['date', 'Date picker', 'select', ['Calendar', 'Compact', 'Range-first']],
      ['upload', 'File upload', 'select', ['Button', 'Dropzone', 'Inline']],
      ['search', 'Search field', 'select', ['Inline', 'Expanded', 'Command', 'Pill']],
    ],
  },
  {
    key: 'tables', title: 'Tables & Data Lists',
    controls: [
      ['density', 'Table density', 'select', ['Compact', 'Normal', 'Comfortable']],
      ['header', 'Header style', 'select', ['Plain', 'Tinted', 'Sticky', 'Elevated']],
      ['zebra', 'Zebra rows', 'select', YES_NO_AUTO],
      ['hover', 'Row hover', 'select', YES_NO_AUTO],
      ['dividers', 'Row dividers', 'select', ['None', 'Hairline', 'Strong']],
      ['rounded', 'Rounded table', 'select', YES_NO_AUTO],
      ['stickyHeader', 'Sticky header', 'select', YES_NO_AUTO],
      ['pagination', 'Pagination style', 'select', ['Pages', 'Prev/Next', 'Load more', 'Infinite']],
      ['filterBar', 'Filter bar', 'select', ['Inline', 'Toolbar', 'Drawer', 'Popover']],
      ['bulk', 'Bulk action toolbar', 'select', ['Sticky', 'Inline', 'Floating', 'Hidden']],
      ['mobile', 'Mobile conversion', 'select', ['Cards', 'Horizontal scroll', 'Collapse']],
    ],
  },
  {
    key: 'tabs', title: 'Tabs / Segmented Controls',
    controls: [
      ['style', 'Tab style', 'select', ['Underline', 'Pill', 'Box', 'Minimal']],
      ['active', 'Active emphasis', 'select', ['Color', 'Fill', 'Underline', 'Weight']],
      ['spacing', 'Tab spacing', 'select', ['Compact', 'Normal', 'Wide']],
      ['mobileScroll', 'Scrollable mobile tabs', 'select', YES_NO_AUTO],
      ['content', 'Tab content', 'select', ['Text only', 'Icon + text']],
      ['badge', 'Badge style', 'select', ['Dot', 'Count', 'Soft', 'Outline']],
      ['vertical', 'Vertical tabs', 'select', ['Allowed', 'Avoid', 'Prefer']],
    ],
  },
  {
    key: 'overlays', title: 'Modal / Drawer / Popup',
    controls: [
      ['modalSize', 'Modal size', 'select', ['Small', 'Medium', 'Large', 'Fullscreen']],
      ['radius', 'Modal radius', 'select', ['Sharp', 'Slight', 'Rounded', 'Large']],
      ['overlayOpacity', 'Overlay opacity', 'select', ['Light', 'Medium', 'Dark']],
      ['blur', 'Background blur', 'select', ['None', 'Soft', 'Strong']],
      ['drawerSide', 'Drawer side', 'select', ['Left', 'Right', 'Bottom']],
      ['sheet', 'Sheet style', 'select', ['Attached', 'Floating', 'Glass']],
      ['confirm', 'Confirmation dialog', 'select', ['Minimal', 'Icon-led', 'Detailed']],
      ['close', 'Close button position', 'select', ['Top right', 'Top left', 'Footer', 'Both']],
    ],
  },
  {
    key: 'hero', title: 'Hero & Landing Sections',
    controls: [
      ['layout', 'Hero layout', 'select', ['Centered', 'Split', 'Image Right', 'Image Left', 'Fullscreen']],
      ['height', 'Hero height', 'select', ['Compact', 'Medium', 'Tall', 'Viewport']],
      ['heading', 'Heading size', 'select', ['Medium', 'Large', 'Display', 'Editorial']],
      ['cta', 'CTA alignment', 'select', ['Left', 'Center', 'Right', 'Split']],
      ['background', 'Background style', 'select', ['Solid', 'Gradient', 'Image', 'Mesh']],
      ['illustration', 'Illustration position', 'select', ['Left', 'Right', 'Background', 'Hidden']],
      ['trust', 'Trust badges', 'select', ['Visible', 'Hidden', 'Contextual']],
      ['stats', 'Stats row', 'select', ['Visible', 'Hidden', 'Contextual']],
      ['features', 'Feature layout', 'select', ['Cards', 'Grid', 'Alternating', 'Bento']],
    ],
  },
  {
    key: 'dashboard', title: 'Dashboard Style',
    controls: [
      ['kpi', 'KPI card style', 'select', ['Minimal', 'Trend-led', 'Icon-led', 'Rich']],
      ['grid', 'Dashboard grid', 'select', ['Fixed', 'Responsive', 'Bento', 'Dense']],
      ['charts', 'Chart card layout', 'select', ['Full width', 'Two column', 'Mixed', 'Compact']],
      ['quick', 'Quick actions', 'select', ['Top', 'Sidebar', 'Floating', 'Inline']],
      ['activity', 'Activity feed', 'select', ['Timeline', 'List', 'Cards', 'Compact']],
      ['stats', 'Stats emphasis', 'select', ['Numbers', 'Charts', 'Trends', 'Balanced']],
      ['density', 'Dashboard density', 'select', COMPACTNESS],
      ['radius', 'Widget radius', 'select', ['Sharp', 'Slight', 'Rounded', 'Large']],
      ['reorder', 'Widget drag/reorder', 'select', YES_NO_AUTO],
    ],
  },
  {
    key: 'charts', title: 'Charts & Data Visualization',
    controls: [
      ['palette', 'Chart palette', 'select', ['Brand', 'Categorical', 'Monochrome', 'Accessible']],
      ['line', 'Line thickness', 'select', ['Thin', 'Medium', 'Bold']],
      ['grid', 'Grid visibility', 'select', ['None', 'Subtle', 'Full']],
      ['legend', 'Legend position', 'select', ['Top', 'Bottom', 'Left', 'Right', 'Hidden']],
      ['tooltip', 'Tooltip style', 'select', ['Minimal', 'Card', 'Rich']],
      ['roundedBars', 'Rounded bars', 'select', YES_NO_AUTO],
      ['areaFill', 'Area fill', 'select', ['None', 'Soft', 'Strong']],
      ['donut', 'Donut thickness', 'select', ['Thin', 'Medium', 'Thick']],
      ['animation', 'Chart animation', 'select', ['None', 'Subtle', 'Expressive']],
      ['mode', 'Color mode', 'select', ['Monochrome', 'Multi-color']],
    ],
  },
  {
    key: 'feedback', title: 'Status & Feedback Components',
    controls: [
      ['success', 'Success style', 'select', ['Toast', 'Banner', 'Inline', 'Dialog']],
      ['warning', 'Warning style', 'select', ['Toast', 'Banner', 'Inline', 'Dialog']],
      ['error', 'Error style', 'select', ['Toast', 'Banner', 'Inline', 'Dialog']],
      ['info', 'Info style', 'select', ['Toast', 'Banner', 'Inline', 'Dialog']],
      ['toastPosition', 'Toast position', 'select', ['Top right', 'Top center', 'Bottom right', 'Bottom center']],
      ['toastStyle', 'Toast style', 'select', ['Minimal', 'Card', 'Colored', 'Glass']],
      ['alert', 'Alert style', 'select', ['Soft', 'Outline', 'Solid', 'Minimal']],
      ['badge', 'Badge style', 'select', ['Soft', 'Solid', 'Outline', 'Dot']],
      ['progress', 'Progress bar', 'select', ['Linear', 'Segmented', 'Circular']],
      ['stepper', 'Stepper style', 'select', ['Horizontal', 'Vertical', 'Compact']],
      ['spinner', 'Loading spinner', 'select', ['Spinner', 'Dots', 'Pulse', 'Bar']],
      ['skeleton', 'Skeleton loader', 'select', ['Simple', 'Shimmer', 'Pulse']],
      ['empty', 'Empty-state design', 'select', ['Minimal', 'Illustrated', 'Action-led']],
    ],
  },
  {
    key: 'brand', title: 'Brand Identity',
    note: 'Upload logo and favicon files in the Images section. These controls tell the designer how to use them.',
    controls: [
      ['logoUsage', 'Logo usage', 'select', ['Use uploaded logo', 'Text logo', 'Mark only', 'Hidden']],
      ['faviconUsage', 'Favicon usage', 'select', ['Use uploaded favicon', 'Derive from logo', 'Simple mark']],
      ['brandName', 'Brand name', 'text'],
      ['primary', 'Brand primary color', 'text'],
      ['secondary', 'Brand secondary color', 'text'],
      ['accent', 'Accent palette', 'select', ['Single accent', 'Dual accent', 'Multi accent']],
      ['gradient', 'Gradient preset', 'select', ['None', 'Subtle', 'Vibrant', 'Mesh']],
      ['font', 'Brand font behavior', 'select', ['Single family', 'Display + body', 'Editorial pairing']],
      ['personality', 'Brand personality', 'select', ['Corporate', 'Friendly', 'Premium', 'Technical', 'Playful', 'Minimal']],
    ],
  },
  {
    key: 'shape', title: 'Shape Language',
    controls: [
      ['global', 'Global shape', 'select', ['Sharp', 'Soft', 'Rounded', 'Pill']],
      ['card', 'Card radius', 'select', ['Sharp', 'Soft', 'Rounded', 'Large']],
      ['input', 'Input radius', 'select', ['Sharp', 'Soft', 'Rounded', 'Pill']],
      ['modal', 'Modal radius', 'select', ['Sharp', 'Soft', 'Rounded', 'Large']],
      ['avatar', 'Avatar shape', 'select', ['Square', 'Rounded', 'Circle']],
      ['image', 'Image radius', 'select', ['Sharp', 'Soft', 'Rounded', 'Large']],
      ['button', 'Button radius', 'select', ['Sharp', 'Soft', 'Rounded', 'Pill']],
      ['badge', 'Badge radius', 'select', ['Sharp', 'Soft', 'Rounded', 'Pill']],
    ],
  },
  {
    key: 'icons', title: 'Icon System',
    controls: [
      ['style', 'Icon style', 'select', ['Outline', 'Filled', 'Duotone']],
      ['library', 'Icon library', 'select', ['Lucide', 'Heroicons', 'Phosphor', 'Material Symbols']],
      ['size', 'Icon size', 'select', ['Small', 'Medium', 'Large']],
      ['stroke', 'Stroke width', 'select', ['Thin', 'Normal', 'Bold']],
      ['background', 'Icon background', 'select', ['None', 'Soft Square', 'Circle']],
      ['colored', 'Colored icons', 'select', YES_NO_AUTO],
      ['semantic', 'Semantic icon colors', 'select', YES_NO_AUTO],
      ['navigation', 'Navigation icon colors', 'select', ['Monochrome', 'Active color', 'Full semantic']],
    ],
  },
  {
    key: 'media', title: 'Images & Media',
    controls: [
      ['radius', 'Image radius', 'select', ['Sharp', 'Slight', 'Rounded', 'Large']],
      ['ratio', 'Image aspect ratio', 'select', ['Original', '1:1', '4:3', '16:9', '3:2']],
      ['fit', 'Image fit', 'select', ['Cover', 'Contain', 'Contextual']],
      ['thumbnail', 'Thumbnail style', 'select', ['Plain', 'Framed', 'Overlay', 'Rounded']],
      ['gallery', 'Gallery layout', 'select', ['Grid', 'Masonry', 'Carousel', 'Bento']],
      ['avatarSize', 'Avatar size', 'select', ['Small', 'Medium', 'Large', 'Responsive']],
      ['avatarShape', 'Avatar shape', 'select', ['Square', 'Rounded', 'Circle']],
      ['illustration', 'Illustration style', 'select', ['Minimal', 'Flat', '3D', 'Technical', 'Editorial']],
      ['overlay', 'Image overlay', 'select', ['None', 'Gradient', 'Tint', 'Darken']],
      ['placeholder', 'Placeholder style', 'select', ['Neutral', 'Skeleton', 'Blurhash', 'Icon']],
    ],
  },
  {
    key: 'backgrounds', title: 'Background System',
    controls: [
      ['page', 'Page background', 'select', ['Solid', 'Gradient', 'Mesh', 'Pattern']],
      ['alternation', 'Section background alternation', 'select', ['None', 'Subtle', 'Strong']],
      ['surfaceHierarchy', 'Surface hierarchy', 'select', ['Flat', '2 levels', '3 levels', 'Layered']],
      ['cardSurface', 'Card surface', 'select', ['Same as page', 'Raised', 'Tinted', 'Glass']],
      ['navbarSurface', 'Navbar surface', 'select', ['Same', 'Raised', 'Glass', 'Transparent']],
      ['sidebarSurface', 'Sidebar surface', 'select', ['Same', 'Tinted', 'Dark', 'Glass']],
      ['glassBlur', 'Glass blur strength', 'select', ['None', 'Soft', 'Medium', 'Strong']],
      ['noise', 'Noise texture', 'select', YES_NO_AUTO],
    ],
  },
  {
    key: 'typography', title: 'Typography Advanced',
    controls: [
      ['mono', 'Mono font', 'text'],
      ['headingWeight', 'Heading weight', 'select', ['500', '600', '700', '800']],
      ['bodyWeight', 'Body weight', 'select', ['400', '450', '500']],
      ['letterSpacing', 'Letter spacing', 'select', ['Tight', 'Normal', 'Wide']],
      ['lineHeight', 'Line height', 'select', ['Tight', 'Normal', 'Relaxed']],
      ['headingScale', 'Heading scale', 'select', ['Compact', 'Standard', 'Large', 'Display']],
      ['bodyScale', 'Body scale', 'select', ['Small', 'Standard', 'Large']],
      ['smallScale', 'Small text scale', 'select', ['Dense', 'Standard', 'Readable']],
      ['uppercaseLabels', 'Uppercase labels', 'select', YES_NO_AUTO],
      ['smoothing', 'Font smoothing', 'select', ['Default', 'Antialiased', 'Subpixel']],
    ],
  },
  {
    key: 'navigationBehavior', title: 'Navigation Behaviour',
    controls: [
      ['breadcrumbs', 'Breadcrumbs', 'select', ['Visible', 'Hidden', 'Contextual']],
      ['backButton', 'Back button', 'select', ['Visible', 'Hidden', 'Contextual']],
      ['pageTitle', 'Page title placement', 'select', ['Header', 'Content', 'Sticky', 'Contextual']],
      ['secondary', 'Secondary navigation', 'select', ['Tabs', 'Sidebar', 'Dropdown', 'None']],
      ['command', 'Command palette', 'select', YES_NO_AUTO],
      ['globalSearch', 'Global search', 'select', YES_NO_AUTO],
      ['fab', 'Floating action button', 'select', ['None', 'Mobile', 'Desktop', 'All']],
      ['bottomNav', 'Bottom mobile navigation', 'select', ['None', 'Primary routes', 'Contextual']],
    ],
  },
  {
    key: 'motion', title: 'Motion & Interaction',
    controls: [
      ['page', 'Page transitions', 'select', ['None', 'Fade', 'Slide', 'Shared element']],
      ['hoverLift', 'Hover lift', 'select', YES_NO_AUTO],
      ['hoverScale', 'Hover scale', 'select', YES_NO_AUTO],
      ['fade', 'Fade interactions', 'select', ['None', 'Subtle', 'Expressive']],
      ['slide', 'Slide interactions', 'select', ['None', 'Subtle', 'Expressive']],
      ['spring', 'Spring animation', 'select', ['None', 'Soft', 'Bouncy']],
      ['dropdown', 'Dropdown animation', 'select', ['None', 'Fade', 'Scale', 'Slide']],
      ['modal', 'Modal animation', 'select', ['None', 'Fade', 'Scale', 'Slide']],
      ['button', 'Button press animation', 'select', ['None', 'Scale', 'Inset', 'Ripple']],
      ['loading', 'Loading animation', 'select', ['Subtle', 'Expressive', 'Minimal']],
      ['reduced', 'Reduced Motion support', 'select', ['Required', 'Preferred', 'Optional']],
    ],
  },
  {
    key: 'accessibility', title: 'Accessibility',
    controls: [
      ['contrast', 'Auto contrast check', 'select', ['Required', 'Preferred']],
      ['wcag', 'WCAG target', 'select', ['AA', 'AAA']],
      ['minFont', 'Minimum font size', 'select', ['14px', '15px', '16px', '18px']],
      ['focus', 'Focus ring style', 'select', ['Strong', 'Soft', 'Brand', 'High contrast']],
      ['keyboard', 'Keyboard indicators', 'select', ['Required', 'Preferred']],
      ['highContrast', 'High contrast mode', 'select', YES_NO_AUTO],
      ['reducedMotion', 'Reduced motion', 'select', ['Required', 'Preferred']],
      ['colorBlind', 'Color-blind-safe palette', 'select', ['Required', 'Preferred']],
      ['touchTarget', 'Minimum touch target', 'select', ['40px', '44px', '48px']],
    ],
  },
  {
    key: 'density', title: 'Design Density',
    controls: [
      ['global', 'Global density', 'select', COMPACTNESS],
      ['rowHeight', 'Global row height', 'select', ['Compact', 'Normal', 'Tall']],
      ['formSpacing', 'Form spacing', 'select', COMPACTNESS],
      ['tableSpacing', 'Table spacing', 'select', COMPACTNESS],
      ['cardPadding', 'Card padding', 'select', COMPACTNESS],
      ['navSpacing', 'Navigation spacing', 'select', COMPACTNESS],
      ['sectionSpacing', 'Section spacing', 'select', COMPACTNESS],
    ],
  },
  {
    key: 'pageSpecific', title: 'Page-specific Customization',
    controls: [
      ['login', 'Login page style', 'select', ['Minimal', 'Split', 'Branded', 'Illustrated']],
      ['signup', 'Signup style', 'select', ['Minimal', 'Wizard', 'Split', 'Branded']],
      ['dashboard', 'Dashboard style', 'select', ['Operational', 'Analytics', 'Executive', 'Workspace']],
      ['list', 'List page style', 'select', ['Table', 'Cards', 'Hybrid', 'Dense']],
      ['detail', 'Detail page style', 'select', ['Tabs', 'Sections', 'Split', 'Drawer-aware']],
      ['settings', 'Settings page style', 'select', ['Sidebar', 'Tabs', 'Sections', 'Search-first']],
      ['checkout', 'Checkout style', 'select', ['Single page', 'Stepper', 'Split summary']],
      ['profile', 'Profile page style', 'select', ['Minimal', 'Card', 'Social', 'Enterprise']],
      ['admin', 'Admin panel style', 'select', ['Dense', 'Enterprise', 'Modern', 'Minimal']],
      ['errors', '404/500 style', 'select', ['Minimal', 'Illustrated', 'Action-led']],
      ['empty', 'Empty page style', 'select', ['Minimal', 'Illustrated', 'Action-led']],
    ],
  },
  {
    key: 'designSystem', title: 'Advanced Design System',
    controls: [
      ['tokens', 'Design Tokens editor', 'select', ['Enabled', 'Hidden']],
      ['radiusScale', 'Global radius token', 'select', ['Sharp', 'Soft', 'Rounded', 'Custom']],
      ['spacingScale', 'Spacing scale', 'select', ['4px', '6px', '8px', 'Custom']],
      ['typeScale', 'Typography scale', 'select', ['Minor third', 'Major third', 'Perfect fourth', 'Custom']],
      ['elevation', 'Elevation scale', 'select', ['Flat', '3 levels', '5 levels']],
      ['surfaces', 'Surface levels', 'select', ['1', '2', '3', '4']],
      ['semanticColors', 'Semantic colors', 'select', ['Standard', 'Extended', 'Custom']],
      ['variants', 'Component variants', 'select', ['Core only', 'Extended', 'Rich']],
      ['presetHandling', 'Preset support', 'select', ['Save custom preset', 'Import/export JSON', 'Both']],
    ],
  },
  {
    key: 'livePreview', title: 'Live Preview Controls',
    controls: [
      ['device', 'Device', 'select', ['Desktop', 'Tablet', 'Phone']],
      ['mode', 'Color mode', 'select', ['Light', 'Dark']],
      ['page', 'Page selector behavior', 'select', ['Current', 'All pages', 'Key pages']],
      ['component', 'Component selector', 'select', ['Enabled', 'Hidden']],
      ['zoom', 'Zoom', 'select', ['50%', '75%', '100%', '125%']],
      ['fullscreen', 'Fullscreen preview', 'select', YES_NO_AUTO],
      ['compare', 'Before / After comparison', 'select', YES_NO_AUTO],
      ['hoverState', 'Hover-state preview', 'select', YES_NO_AUTO],
      ['errorState', 'Error-state preview', 'select', YES_NO_AUTO],
      ['loadingState', 'Loading-state preview', 'select', YES_NO_AUTO],
    ],
  },
  {
    key: 'aiAssist', title: 'AI Assisted Design',
    controls: [
      ['actions', 'AI design intentions', 'multi', [
        'Make it more premium', 'Make it more minimal', 'Increase readability',
        'Improve spacing', 'Improve accessibility', 'Make it look like SaaS',
        'Make it more enterprise', 'Make it more playful', 'Modernize this design',
        'Generate 3 variations', 'Auto-fix bad contrast', 'Auto-balance spacing',
        'Auto-select component styles', 'Use app-type-aware suggestions',
      ]],
    ],
  },
]

function humanize(key) {
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase())
}

export function advancedCustomizationDirection(value = {}) {
  const lines = []
  for (const section of SECTIONS) {
    const current = value?.[section.key] || {}
    const settings = []
    for (const control of section.controls) {
      const [key, label] = control
      const chosen = current[key]
      if (Array.isArray(chosen) && chosen.length) settings.push(`${label}: ${chosen.join(', ')}`)
      else if (chosen !== undefined && chosen !== null && String(chosen).trim()) settings.push(`${label}: ${chosen}`)
    }
    if (settings.length) lines.push(`${section.title}: ${settings.join('; ')}.`)
  }
  return lines.length
    ? `Advanced design system instructions:\n${lines.join('\n')}`
    : ''
}

function Field({ sectionKey, definition, current, onChange }) {
  const [key, label, type = 'select', options = []] = definition
  const value = current?.[key] ?? (type === 'multi' ? [] : '')

  if (type === 'text') {
    return (
      <label className="block text-xs font-medium text-muted">
        {label}
        <input
          value={value}
          onChange={e => onChange(sectionKey, key, e.target.value)}
          placeholder="Auto"
          className="mt-1.5 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
        />
      </label>
    )
  }

  if (type === 'multi') {
    const picked = Array.isArray(value) ? value : []
    return (
      <div className="sm:col-span-2">
        <p className="mb-2 text-xs font-medium text-muted">{label}</p>
        <div className="flex flex-wrap gap-2">
          {options.map(option => {
            const active = picked.includes(option)
            return (
              <button
                key={option}
                type="button"
                onClick={() => onChange(sectionKey, key,
                  active ? picked.filter(item => item !== option) : [...picked, option])}
                className={`rounded-full border px-3 py-1.5 text-xs transition ${active
                  ? 'border-accent bg-accent/15 text-ink'
                  : 'border-line bg-panel2 text-muted hover:border-accent/60 hover:text-ink'}`}
              >
                {option}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  return (
    <label className="block text-xs font-medium text-muted">
      {label}
      <select
        value={value}
        onChange={e => onChange(sectionKey, key, e.target.value)}
        className="mt-1.5 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
      >
        <option value="">Auto</option>
        {options.map(option => <option key={option} value={option}>{option}</option>)}
      </select>
    </label>
  )
}

export default function AdvancedDesignCustomize({ value = {}, onChange }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(() => new Set(['layout', 'responsive', 'cards', 'forms']))

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return SECTIONS
    return SECTIONS.filter(section => {
      if (section.title.toLowerCase().includes(needle)) return true
      return section.controls.some(control => `${control[1]} ${(control[3] || []).join(' ')}`.toLowerCase().includes(needle))
    })
  }, [query])

  function setValue(section, key, next) {
    onChange?.({
      ...value,
      [section]: {
        ...(value?.[section] || {}),
        [key]: next,
      },
    })
  }

  function toggle(section) {
    setOpen(previous => {
      const next = new Set(previous)
      if (next.has(section)) next.delete(section)
      else next.add(section)
      return next
    })
  }

  const configured = useMemo(() => Object.values(value || {}).reduce((total, section) => {
    if (!section || typeof section !== 'object') return total
    return total + Object.values(section).filter(item => Array.isArray(item) ? item.length : String(item || '').trim()).length
  }, 0), [value])

  return (
    <div className="rounded-xl border border-line bg-panel p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-accent" />
            <p className="text-sm font-semibold text-ink">Full design system controls</p>
          </div>
          <p className="mt-1 text-xs text-muted">
            Component-level, page-level, responsive, accessibility and interaction controls. Unset fields stay automatic.
          </p>
        </div>
        <span className="text-[11px] text-muted2">{configured} configured</span>
      </div>

      <div className="relative mt-4">
        <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted2" />
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search design controls…"
          className="w-full rounded-lg border border-line bg-panel2 py-2 pl-9 pr-3 text-sm text-ink outline-none focus:border-accent"
        />
      </div>

      <div className="mt-4 space-y-2">
        {visible.map(section => {
          const expanded = open.has(section.key) || Boolean(query.trim())
          const sectionValue = value?.[section.key] || {}
          const sectionCount = Object.values(sectionValue).filter(item => Array.isArray(item) ? item.length : String(item || '').trim()).length
          return (
            <div key={section.key} className="overflow-hidden rounded-xl border border-line bg-panel2/60">
              <button
                type="button"
                onClick={() => toggle(section.key)}
                className="flex w-full items-center justify-between gap-3 px-3.5 py-3 text-left hover:bg-panel2"
              >
                <span className="flex items-center gap-2 text-sm font-medium text-ink">
                  {expanded ? <ChevronDown className="size-4 text-muted" /> : <ChevronRight className="size-4 text-muted" />}
                  {section.title}
                </span>
                <span className="text-[10.5px] text-muted2">
                  {sectionCount ? `${sectionCount} set` : `${section.controls.length} controls`}
                </span>
              </button>
              {expanded && (
                <div className="border-t border-line px-3.5 py-4">
                  {section.note && <p className="mb-3 text-[11px] leading-relaxed text-muted2">{section.note}</p>}
                  <div className="grid gap-3 sm:grid-cols-2">
                    {section.controls.map(control => (
                      <Field
                        key={`${section.key}-${control[0]}`}
                        sectionKey={section.key}
                        definition={control}
                        current={sectionValue}
                        onChange={setValue}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )
        })}
        {!visible.length && (
          <p className="rounded-lg border border-line bg-panel2 px-4 py-6 text-center text-sm text-muted">
            No design controls match “{query}”.
          </p>
        )}
      </div>
    </div>
  )
}
