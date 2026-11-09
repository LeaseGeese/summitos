import QtQuick 2.0;

Rectangle {
    property string glyph: ""
    property string title: ""
    property string body: ""
    anchors.centerIn: parent
    width: Math.min(parent.width - 60, 640); height: col.height + 64
    radius: 26; color: "#d9ffffff"; border.color: "#ffffff"; border.width: 1
    Column {
        id: col; anchors.centerIn: parent; width: parent.width - 72; spacing: 14
        Text { text: glyph; font.pixelSize: 54; anchors.horizontalCenter: parent.horizontalCenter }
        Text { text: title; width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
               font.pixelSize: 28; font.weight: Font.Bold; color: "#1d1d1f"; font.family: "Inter" }
        Text { text: body; width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
               font.pixelSize: 17; color: "#3a3a3f"; lineHeight: 1.25; font.family: "Inter" }
    }
}
