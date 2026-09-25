import QtQuick
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.Particles3D
import Jarvis3D
import "palette.js" as Palette

// Real-time 3D arc-reactor: HDR core with bloom, holographic rings, a glass shell and a
// particle halo. Colour, spin speed and energy follow the assistant state and your voice.
Item {
    id: root
    property string assistantState: "IDLE"
    property real level: 0.0          // live microphone energy 0..1
    property bool animate: true
    signal activated()

    readonly property color tint: Palette.stateColor(assistantState)
    readonly property real speed: Palette.speed(assistantState)
    readonly property bool busy: Palette.isBusy(assistantState)
    property real phase: 0.0
    property real energy: 0.0          // smoothed level (+ synthetic pulse while speaking)
    property real tiltX: 0.0
    property real tiltY: 0.0
    property real hover: 0.0

    Behavior on tiltX { SpringAnimation { spring: 2.2; damping: 0.28 } }
    Behavior on tiltY { SpringAnimation { spring: 2.2; damping: 0.28 } }
    Behavior on hover { NumberAnimation { duration: 250 } }

    function glow(c, k) { return Qt.vector3d(c.r * k, c.g * k, c.b * k) }

    FrameAnimation {
        running: root.animate && root.visible
        onTriggered: {
            var dt = Math.min(frameTime, 0.05)
            root.phase += dt * root.speed
            var speaking = root.assistantState === "SPEAKING"
                ? 0.35 + 0.3 * Math.abs(Math.sin(root.phase * 7.3)) * Math.abs(Math.sin(root.phase * 3.1 + 1.0)) : 0.0
            var target = Math.max(Math.min(1.0, root.level * 1.4), speaking)
            // fast attack, slow release: feels alive without jitter
            var k = target > root.energy ? 0.45 : 0.08
            root.energy += (target - root.energy) * k
        }
    }

    View3D {
        id: view
        anchors.fill: parent
        camera: camera

        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
            tonemapMode: SceneEnvironment.TonemapModeFilmic
            glowEnabled: true
            glowQualityHigh: true
            glowUseBicubicUpscale: true
            glowStrength: 0.9
            glowIntensity: 0.55 + root.energy * 0.35
            glowBloom: 0.06
            glowBlendMode: 0          // Additive
            glowHDRMinimumValue: 1.0
            glowLevel: 0x2 | 0x4 | 0x8
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 820)
            fieldOfView: 40
            clipNear: 10
            clipFar: 2000
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-35, -40, 0)
            brightness: 1.4
        }

        PointLight {
            color: root.tint
            brightness: 0.8 + root.energy * 3.0
            quadraticFade: 0.6
        }

        Node {
            id: rig
            eulerRotation: Qt.vector3d(root.tiltX, root.tiltY, 0)
            scale: Qt.vector3d(1, 1, 1).times(1.0 + root.energy * 0.08 + root.hover * 0.04)

            // --- hot core -------------------------------------------------------------
            Model {
                source: "#Sphere"
                scale: Qt.vector3d(1, 1, 1).times(0.36 + root.energy * 0.12)
                materials: PrincipledMaterial {
                    lighting: PrincipledMaterial.NoLighting
                    baseColor: "white"
                    emissiveFactor: Qt.vector3d(2.2, 2.2, 2.2)
                }
            }
            Model {
                source: "#Sphere"
                scale: Qt.vector3d(1, 1, 1).times(0.72 + root.energy * 0.22 + 0.03 * Math.sin(root.phase * 2.0))
                materials: PrincipledMaterial {
                    baseColor: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.55)
                    alphaMode: PrincipledMaterial.Blend
                    emissiveFactor: root.glow(root.tint, 1.05 + root.energy * 1.2)
                    roughness: 0.3
                }
            }

            // --- glass shell ------------------------------------------------------------
            Model {
                source: "#Sphere"
                scale: Qt.vector3d(2.0, 2.0, 2.0)
                materials: PrincipledMaterial {
                    baseColor: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.07)
                    alphaMode: PrincipledMaterial.Blend
                    metalness: 0.0
                    roughness: 0.04
                    specularAmount: 1.0
                    clearcoatAmount: 1.0
                    clearcoatRoughnessAmount: 0.02
                    
                }
            }

            // --- holographic rings ---------------------------------------------------------
            Model {   // gyroscope ring 1
                geometry: TubeRingGeometry { radius: 128; tube: 1.3 }
                eulerRotation: Qt.vector3d(72, root.phase * 38, 0)
                materials: PrincipledMaterial {
                    lighting: PrincipledMaterial.NoLighting
                    baseColor: root.tint
                    emissiveFactor: root.glow(root.tint, 1.15)
                }
            }
            Model {   // gyroscope ring 2
                geometry: TubeRingGeometry { radius: 150; tube: 0.9 }
                eulerRotation: Qt.vector3d(-58, 20, root.phase * -26)
                materials: PrincipledMaterial {
                    lighting: PrincipledMaterial.NoLighting
                    baseColor: root.tint
                    emissiveFactor: root.glow(root.tint, 0.9)
                }
            }
            Model {   // fine dashed ring, faces the camera
                geometry: HudRingGeometry { innerRadius: 172; outerRadius: 178; dashes: 72; gap: 0.45 }
                eulerRotation: Qt.vector3d(0, 0, root.phase * 12)
                scale: Qt.vector3d(1, 1, 1).times(1.0 + root.energy * 0.06)
                materials: PrincipledMaterial {
                    lighting: PrincipledMaterial.NoLighting
                    cullMode: Material.NoCulling
                    alphaMode: PrincipledMaterial.Blend
                    baseColor: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.85)
                    emissiveFactor: root.glow(root.tint, 0.7)
                }
            }
            Model {   // three bold arcs, spin faster when thinking
                geometry: HudRingGeometry { innerRadius: 188; outerRadius: 199; dashes: 3; gap: 0.32 }
                eulerRotation: Qt.vector3d(0, 0, -root.phase * (root.busy ? 70 : 22))
                materials: PrincipledMaterial {
                    lighting: PrincipledMaterial.NoLighting
                    cullMode: Material.NoCulling
                    alphaMode: PrincipledMaterial.Blend
                    baseColor: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.55 + root.energy * 0.4)
                    emissiveFactor: root.glow(root.tint, 0.6 + root.energy * 0.8)
                }
            }
            Model {   // outer tick marks
                geometry: HudRingGeometry { innerRadius: 212; outerRadius: 220; dashes: 120; gap: 0.7 }
                eulerRotation: Qt.vector3d(0, 0, root.phase * -5)
                materials: PrincipledMaterial {
                    lighting: PrincipledMaterial.NoLighting
                    cullMode: Material.NoCulling
                    alphaMode: PrincipledMaterial.Blend
                    baseColor: Qt.rgba(root.tint.r, root.tint.g, root.tint.b, 0.35)
                }
            }
            Model {   // voice ring: expands with your voice
                geometry: HudRingGeometry { innerRadius: 100; outerRadius: 102.5; dashes: 1 }
                scale: Qt.vector3d(1, 1, 1).times(1.0 + root.energy * 0.55)
                opacity: 0.15 + root.energy * 0.85
                materials: PrincipledMaterial {
                    lighting: PrincipledMaterial.NoLighting
                    cullMode: Material.NoCulling
                    alphaMode: PrincipledMaterial.Blend
                    baseColor: root.tint
                    emissiveFactor: root.glow(root.tint, 1.3)
                }
            }

            // --- particle halo --------------------------------------------------------------
            ParticleSystem3D {
                running: root.animate && root.visible

                ModelParticle3D {
                    id: spark
                    maxAmount: 260
                    color: root.tint
                    colorVariation: Qt.vector4d(0.1, 0.1, 0.1, 0.3)
                    fadeInDuration: 400
                    fadeOutDuration: 900
                    delegate: Model {
                        source: "#Sphere"
                        scale: Qt.vector3d(0.028, 0.028, 0.028)
                        materials: PrincipledMaterial {
                            lighting: PrincipledMaterial.NoLighting
                            baseColor: "white"
                        }
                    }
                }
                ParticleEmitter3D {
                    particle: spark
                    shape: ParticleShape3D { type: ParticleShape3D.Sphere; extents: Qt.vector3d(120, 120, 120); fill: false }
                    emitRate: 28 + root.energy * 160 + (root.busy ? 40 : 0)
                    lifeSpan: 2600
                    lifeSpanVariation: 900
                    particleScaleVariation: 0.6
                    velocity: VectorDirection3D {
                        direction: Qt.vector3d(0, 8, 0)
                        directionVariation: Qt.vector3d(30 + root.energy * 60, 30 + root.energy * 60, 30)
                    }
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onPositionChanged: function(mouse) {
            root.tiltY = (mouse.x / width - 0.5) * 34
            root.tiltX = (mouse.y / height - 0.5) * 26
        }
        onEntered: root.hover = 1.0
        onExited: { root.hover = 0.0; root.tiltX = 0; root.tiltY = 0 }
        onClicked: root.activated()
    }
}
