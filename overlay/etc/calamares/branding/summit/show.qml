import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation {
    id: presentation
    function onActivate() { presentation.currentSlide = 0; }
    function onLeave() { }

    Timer {
        interval: 8000; repeat: true
        running: presentation.activatedInCalamares
        onTriggered: presentation.goToNextSlide()
    }

    Image { anchors.fill: parent; source: "slide-bg.jpg"; fillMode: Image.PreserveAspectCrop; z: -2 }
    Rectangle { anchors.fill: parent; color: "#1b1240"; opacity: 0.35; z: -1 }

    Slide { Card { glyph: "🏔️"; title: "Welcome to Summit 2.0"
                   body: "Installing takes 10 to 20 minutes. Your Mac-style desktop, is almost ready." } }
    Slide { Card { glyph: "🎨"; title: "Seven accent colours"
                   body: "Pick blue, purple, pink, orange, yellow, green or silver in Settings → Appearance. Light, Dark, or Auto at sunset." } }
    Slide { Card { glyph: "💧"; title: "Liquid Glass"
                   body: "The menu bar, dock, menus, Spotlight and Control Center are translucent glass that picks up your wallpaper." } }
    Slide { Card { glyph: "💻"; title: "Works with your Mac"
                   body: "File Sharing in Finder, AirPlay to this screen, Time Machine backups and keyboard sharing, all in Settings → Sharing." } }
    Slide { Card { glyph: "💽"; title: "Your hard drive becomes iMac HD"
                   body: "After you sign in, Summit offers to turn the internal hard drive into extra space for your files and backups." } }
    Slide { Card { glyph: "⌘"; title: "Shortcuts to know"
                   body: "⌘ Space  Spotlight      ⌘ A  Launchpad\n⌘ ⇧ 4  Screenshot      ⌘ Q  Close a window" } }
}
