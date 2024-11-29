/// <reference types="@webgpu/types" />

import { useEffect, useRef } from "react";
import { mat4, vec3 } from "gl-matrix";

interface Mesh {
  vertices: number[][];
  indices: number[];
  normals: number[][];
  colors?: number[][];
  material_id?: string;
}

interface ProcessedIFC {
  meshes: Mesh[];
  bounds: number[][];
  element_count: number;
}

const vertexShader = `
struct Uniforms {
  modelViewProjectionMatrix: mat4x4<f32>,
  normalMatrix: mat4x4<f32>,
  cameraPosition: vec4<f32>,
}

@binding(0) @group(0) var<uniform> uniforms: Uniforms;

struct VertexInput {
  @location(0) position: vec3<f32>,
  @location(1) normal: vec3<f32>,
}

struct VertexOutput {
  @builtin(position) position: vec4<f32>,
  @location(0) worldNormal: vec3<f32>,
  @location(1) worldPosition: vec3<f32>,
}

@vertex
fn main(input: VertexInput) -> VertexOutput {
  var output: VertexOutput;
  output.position = uniforms.modelViewProjectionMatrix * vec4<f32>(input.position, 1.0);
  output.worldNormal = normalize((uniforms.normalMatrix * vec4<f32>(input.normal, 0.0)).xyz);
  output.worldPosition = input.position;
  return output;
}`;

const fragmentShader = `
@fragment
fn main(
  @location(0) worldNormal: vec3<f32>,
  @location(1) worldPosition: vec3<f32>,
) -> @location(0) vec4<f32> {
  let baseColor = vec3<f32>(0.75, 0.75, 0.75);  // Light gray base color
  let ambientLight = vec3<f32>(0.2, 0.2, 0.25);  // Slight blue tint in ambient
  
  // Key light (warm sunlight)
  let lightDir1 = normalize(vec3<f32>(1.0, 1.0, 0.5));
  let lightColor1 = vec3<f32>(1.0, 0.95, 0.8);
  let diffuse1 = max(dot(normalize(worldNormal), lightDir1), 0.0);
  
  // Fill light (cool sky light)
  let lightDir2 = normalize(vec3<f32>(-1.0, 0.5, -0.2));
  let lightColor2 = vec3<f32>(0.6, 0.7, 1.0);
  let diffuse2 = max(dot(normalize(worldNormal), lightDir2), 0.0) * 0.5;
  
  // Fresnel-like edge highlight
  let viewDir = normalize(vec3<f32>(0.0, 0.0, 1.0) - worldPosition);
  let fresnel = pow(1.0 - max(dot(normalize(worldNormal), viewDir), 0.0), 3.0);
  
  // Combine lighting
  let finalColor = baseColor * (
    ambientLight +
    lightColor1 * diffuse1 * 0.7 +
    lightColor2 * diffuse2 * 0.3 +
    vec3<f32>(1.0) * fresnel * 0.2
  );
  
  return vec4<f32>(finalColor, 1.0);
}`;

// Add ViewControls component
const ViewControls = ({ camera }: { camera: Camera }) => {
  return (
    <div className="absolute bottom-4 right-4 flex flex-col gap-2">
      <div className="bg-gray-800/80 backdrop-blur-sm p-2 rounded-lg flex flex-col gap-2">
        <button
          onClick={() => camera.setStandardView("front")}
          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm font-medium transition-colors"
          title="Front View (F)"
        >
          Front
        </button>
        <button
          onClick={() => camera.setStandardView("top")}
          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm font-medium transition-colors"
          title="Top View (T)"
        >
          Top
        </button>
        <button
          onClick={() => camera.setStandardView("side")}
          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm font-medium transition-colors"
          title="Side View (S)"
        >
          Side
        </button>
        <button
          onClick={() => camera.setStandardView("reset")}
          className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm font-medium transition-colors"
          title="Reset View (R)"
        >
          Reset
        </button>
      </div>
    </div>
  );
};

export default function IFCViewer({ data }: { data: ProcessedIFC }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<WebGPURenderer | null>(null);

  useEffect(() => {
    if (!canvasRef.current || !data) return;

    const init = async () => {
      const renderer = new WebGPURenderer(canvasRef.current!);
      await renderer.initialize();
      await renderer.loadGeometry(data);
      rendererRef.current = renderer;
      renderer.render();
    };

    init();

    return () => {
      rendererRef.current?.dispose();
    };
  }, [data]);

  const handleContextMenu = (event: React.MouseEvent) => {
    event.preventDefault();
  };

  return (
    <div className="relative w-full h-full">
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{ touchAction: "none" }}
        onContextMenu={handleContextMenu}
      />
      {rendererRef.current && (
        <ViewControls camera={rendererRef.current.camera} />
      )}
    </div>
  );
}

class WebGPURenderer {
  private canvas: HTMLCanvasElement;
  private device!: GPUDevice;
  private context!: GPUCanvasContext;
  private pipeline!: GPURenderPipeline;
  private vertexBuffers: GPUBuffer[] = [];
  private indexBuffers: GPUBuffer[] = [];
  private uniformBuffer!: GPUBuffer;
  private bindGroup!: GPUBindGroup;
  private depthTexture!: GPUTexture;
  private msaaTexture!: GPUTexture;
  private camera: Camera;
  private canvasFormat!: GPUTextureFormat;
  private sampleCount: number = 4; // MSAA sample count
  private destroyed: boolean = false;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.camera = new Camera();
    this.camera.attachControls(canvas);
    this.setupCanvasSize();
  }

  private setupCanvasSize() {
    // Get the display's pixel ratio
    const pixelRatio = window.devicePixelRatio || 1;

    // Get the size of the canvas in CSS pixels
    const rect = this.canvas.getBoundingClientRect();

    // Set the canvas size in physical pixels
    this.canvas.width = rect.width * pixelRatio;
    this.canvas.height = rect.height * pixelRatio;

    // Update camera aspect ratio
    this.camera.setAspectRatio(rect.width / rect.height);
  }

  async initialize() {
    if (!navigator.gpu) {
      throw new Error("WebGPU not supported");
    }

    const adapter = await navigator.gpu.requestAdapter({
      powerPreference: "high-performance",
    });

    if (!adapter) {
      throw new Error("No appropriate GPUAdapter found");
    }

    this.device = await adapter.requestDevice({
      requiredFeatures: ["texture-compression-bc"],
      requiredLimits: {
        maxStorageBufferBindingSize: adapter.limits.maxStorageBufferBindingSize,
        maxBufferSize: adapter.limits.maxBufferSize,
      },
    });

    this.context = this.canvas.getContext("webgpu") as GPUCanvasContext;
    if (!this.context) {
      throw new Error("Failed to get WebGPU context");
    }

    this.canvasFormat = navigator.gpu.getPreferredCanvasFormat();

    // Configure the swap chain with alpha mode for better quality
    this.context.configure({
      device: this.device,
      format: this.canvasFormat,
      alphaMode: "premultiplied",
      usage: GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.COPY_SRC,
    });

    await this.createMSAATexture();
    await this.createDepthTexture();
    await this.createPipeline();
    await this.createUniformBuffer();

    // Add resize observer
    const resizeObserver = new ResizeObserver(() => {
      this.setupCanvasSize();
      this.createMSAATexture();
      this.createDepthTexture();
    });
    resizeObserver.observe(this.canvas);
  }

  private async createMSAATexture() {
    if (this.msaaTexture) {
      this.msaaTexture.destroy();
    }

    this.msaaTexture = this.device.createTexture({
      size: {
        width: this.canvas.width,
        height: this.canvas.height,
        depthOrArrayLayers: 1,
      },
      format: this.canvasFormat,
      usage: GPUTextureUsage.RENDER_ATTACHMENT,
      sampleCount: this.sampleCount,
    });
  }

  private async createDepthTexture() {
    if (this.depthTexture) {
      this.depthTexture.destroy();
    }

    this.depthTexture = this.device.createTexture({
      size: {
        width: this.canvas.width,
        height: this.canvas.height,
        depthOrArrayLayers: 1,
      },
      format: "depth24plus",
      usage: GPUTextureUsage.RENDER_ATTACHMENT,
      sampleCount: this.sampleCount,
    });
  }

  private async createPipeline() {
    this.pipeline = this.device.createRenderPipeline({
      layout: "auto",
      vertex: {
        module: this.device.createShaderModule({ code: vertexShader }),
        entryPoint: "main",
        buffers: [
          {
            arrayStride: 24,
            attributes: [
              { format: "float32x3", offset: 0, shaderLocation: 0 },
              { format: "float32x3", offset: 12, shaderLocation: 1 },
            ],
          },
        ],
      },
      fragment: {
        module: this.device.createShaderModule({ code: fragmentShader }),
        entryPoint: "main",
        targets: [
          {
            format: this.canvasFormat,
            blend: {
              color: {
                srcFactor: "src-alpha",
                dstFactor: "one-minus-src-alpha",
                operation: "add",
              },
              alpha: {
                srcFactor: "one",
                dstFactor: "one-minus-src-alpha",
                operation: "add",
              },
            },
          },
        ],
      },
      primitive: {
        topology: "triangle-list",
        cullMode: "back",
      },
      depthStencil: {
        format: "depth24plus",
        depthWriteEnabled: true,
        depthCompare: "less",
      },
      multisample: {
        count: this.sampleCount,
      },
    });
  }

  private async createUniformBuffer() {
    this.uniformBuffer = this.device.createBuffer({
      size: 144, // 4x4 matrix * 2 + vec4 camera position
      usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });

    this.bindGroup = this.device.createBindGroup({
      layout: this.pipeline.getBindGroupLayout(0),
      entries: [
        {
          binding: 0,
          resource: { buffer: this.uniformBuffer },
        },
      ],
    });
  }

  async loadGeometry(data: ProcessedIFC) {
    // Clean up existing buffers
    this.vertexBuffers.forEach((buffer) => buffer.destroy());
    this.indexBuffers.forEach((buffer) => buffer.destroy());
    this.vertexBuffers = [];
    this.indexBuffers = [];

    // Set camera target to bottom left of model bounds
    this.camera.setModelBounds(data.bounds);

    for (const mesh of data.meshes) {
      const vertexData = new Float32Array(mesh.vertices.length * 6);
      for (let i = 0; i < mesh.vertices.length; i++) {
        vertexData[i * 6] = mesh.vertices[i][0];
        vertexData[i * 6 + 1] = mesh.vertices[i][1];
        vertexData[i * 6 + 2] = mesh.vertices[i][2];
        vertexData[i * 6 + 3] = mesh.normals[i][0];
        vertexData[i * 6 + 4] = mesh.normals[i][1];
        vertexData[i * 6 + 5] = mesh.normals[i][2];
      }

      const vertexBuffer = this.device.createBuffer({
        size: vertexData.byteLength,
        usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
      });
      this.device.queue.writeBuffer(vertexBuffer, 0, vertexData);
      this.vertexBuffers.push(vertexBuffer);

      const indexData = new Uint32Array(mesh.indices);
      const indexBuffer = this.device.createBuffer({
        size: indexData.byteLength,
        usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
      });
      this.device.queue.writeBuffer(indexBuffer, 0, indexData);
      this.indexBuffers.push(indexBuffer);
    }
  }

  render = () => {
    if (this.destroyed) return;

    try {
      const commandEncoder = this.device.createCommandEncoder();
      const currentTexture = this.context.getCurrentTexture();

      const renderPassDescriptor: GPURenderPassDescriptor = {
        colorAttachments: [
          {
            view: this.msaaTexture.createView(),
            resolveTarget: currentTexture.createView(),
            clearValue: { r: 0.15, g: 0.15, b: 0.2, a: 1.0 },
            loadOp: "clear",
            storeOp: "store",
          },
        ],
        depthStencilAttachment: {
          view: this.depthTexture.createView(),
          depthClearValue: 1.0,
          depthLoadOp: "clear",
          depthStoreOp: "store",
        },
      };

      const renderPass = commandEncoder.beginRenderPass(renderPassDescriptor);

      // Update uniforms
      const viewProjectionMatrix = this.camera.getViewProjectionMatrix();
      const normalMatrix = this.camera.getNormalMatrix();
      const cameraPosition = new Float32Array([
        ...this.camera.getPosition(),
        1.0,
      ]);

      this.device.queue.writeBuffer(
        this.uniformBuffer,
        0,
        viewProjectionMatrix
      );
      this.device.queue.writeBuffer(this.uniformBuffer, 64, normalMatrix);
      this.device.queue.writeBuffer(this.uniformBuffer, 128, cameraPosition);

      renderPass.setPipeline(this.pipeline);
      renderPass.setBindGroup(0, this.bindGroup);

      for (let i = 0; i < this.vertexBuffers.length; i++) {
        renderPass.setVertexBuffer(0, this.vertexBuffers[i]);
        renderPass.setIndexBuffer(this.indexBuffers[i], "uint32");
        renderPass.drawIndexed(this.indexBuffers[i].size / 4);
      }

      renderPass.end();
      this.device.queue.submit([commandEncoder.finish()]);

      requestAnimationFrame(this.render);
    } catch (error) {
      console.error("Render error:", error);
      this.destroyed = true;
    }
  };

  dispose() {
    this.destroyed = true;
    this.camera.detachControls(this.canvas);
    this.vertexBuffers.forEach((buffer) => buffer.destroy());
    this.indexBuffers.forEach((buffer) => buffer.destroy());
    this.uniformBuffer.destroy();
    this.depthTexture.destroy();
    this.msaaTexture.destroy();
  }
}

class Camera {
  private position: vec3;
  private target: vec3;
  private up: vec3;
  private aspect: number;
  private fov: number;
  private near: number;
  private far: number;
  private modelBounds: [vec3, vec3] | null = null;

  // Camera control properties
  private isDragging: boolean = false;
  private isPanning: boolean = false;
  private lastMouseX: number = 0;
  private lastMouseY: number = 0;
  private rotationSpeed: number = 0.003;
  private panSpeed: number = 0.005;
  private zoomSpeed: number = 0.1;
  private minDistance: number = 1;
  private maxDistance: number = 1000;
  private minPolarAngle: number = 0.1;
  private maxPolarAngle: number = Math.PI / 2.1;
  // Initialize with 45° view flipped 90° around horizontal axis
  private currentPolarAngle: number = Math.PI / 4; // 45° for height
  private currentAzimuthAngle: number = (-Math.PI * 3) / 4; // -135° rotation (-90° more than previous)

  constructor() {
    this.position = vec3.create();
    this.target = vec3.create();
    this.up = vec3.fromValues(0, 1, 0);
    this.aspect = 1;
    this.fov = Math.PI / 4;
    this.near = 0.1;
    this.far = 1000.0;
  }

  setModelBounds(bounds: number[][]) {
    const minBound = vec3.fromValues(bounds[0][0], bounds[0][1], bounds[0][2]);
    const maxBound = vec3.fromValues(bounds[1][0], bounds[1][1], bounds[1][2]);
    this.modelBounds = [minBound, maxBound];

    // Calculate model dimensions
    const dimensions = vec3.sub(vec3.create(), maxBound, minBound);
    const maxDimension = Math.max(dimensions[0], dimensions[1], dimensions[2]);

    // Set initial target to bottom left (minimum X and Z, minimum Y)
    this.target = vec3.fromValues(minBound[0], minBound[1], minBound[2]);

    // Position camera based on model size
    this.updateCameraPosition(maxDimension * 2);
  }

  private updateCameraPosition(distance: number = 30) {
    if (!this.modelBounds) {
      // Default position if no bounds set
      const x =
        distance *
        Math.sin(this.currentPolarAngle) *
        Math.cos(this.currentAzimuthAngle);
      const y = distance * Math.cos(this.currentPolarAngle);
      const z =
        distance *
        Math.sin(this.currentPolarAngle) *
        Math.sin(this.currentAzimuthAngle);
      this.position = vec3.fromValues(x, z, y);
      return;
    }

    // Calculate camera position relative to target (bottom left corner)
    const x =
      this.target[0] +
      distance *
        Math.sin(this.currentPolarAngle) *
        Math.cos(this.currentAzimuthAngle);
    const y = this.target[1] + distance * Math.cos(this.currentPolarAngle);
    const z =
      this.target[2] +
      distance *
        Math.sin(this.currentPolarAngle) *
        Math.sin(this.currentAzimuthAngle);

    // Swap Y and Z coordinates and maintain flipped orientation
    this.position = vec3.fromValues(x, z, y);
  }

  private handlePan(deltaX: number, deltaY: number) {
    // Calculate pan direction in world space
    const right = vec3.cross(
      vec3.create(),
      vec3.sub(vec3.create(), this.position, this.target),
      this.up
    );
    vec3.normalize(right, right);
    const up = vec3.cross(
      vec3.create(),
      right,
      vec3.sub(vec3.create(), this.position, this.target)
    );
    vec3.normalize(up, up);

    // Pan speed based on distance to target (faster when zoomed out)
    const distance = vec3.distance(this.position, this.target);
    const adjustedPanSpeed = this.panSpeed * distance;

    const panX = vec3.scale(
      vec3.create(),
      right,
      (-deltaX / this.rotationSpeed) * adjustedPanSpeed
    );
    const panY = vec3.scale(
      vec3.create(),
      up,
      (deltaY / this.rotationSpeed) * adjustedPanSpeed
    );

    // Update both position and target to maintain relative position
    vec3.add(this.position, this.position, panX);
    vec3.add(this.position, this.position, panY);
    vec3.add(this.target, this.target, panX);
    vec3.add(this.target, this.target, panY);
  }

  attachControls(canvas: HTMLCanvasElement) {
    canvas.addEventListener("mousedown", this.handleMouseDown);
    window.addEventListener("mousemove", this.handleMouseMove);
    window.addEventListener("mouseup", this.handleMouseUp);
    canvas.addEventListener("wheel", this.handleWheel);
    window.addEventListener("keydown", this.handleKeyDown);
  }

  detachControls(canvas: HTMLCanvasElement) {
    canvas.removeEventListener("mousedown", this.handleMouseDown);
    window.removeEventListener("mousemove", this.handleMouseMove);
    window.removeEventListener("mouseup", this.handleMouseUp);
    canvas.removeEventListener("wheel", this.handleWheel);
    window.removeEventListener("keydown", this.handleKeyDown);
  }

  private handleMouseDown = (event: MouseEvent) => {
    if (event.button === 0) {
      // Left click - Orbit
      this.isDragging = true;
    } else if (event.button === 2 || event.button === 1) {
      // Right click or Middle click - Pan
      this.isPanning = true;
    }
    this.lastMouseX = event.clientX;
    this.lastMouseY = event.clientY;
  };

  private handleMouseMove = (event: MouseEvent) => {
    if (!this.isDragging && !this.isPanning) return;

    const deltaX = (event.clientX - this.lastMouseX) * this.rotationSpeed;
    const deltaY = (event.clientY - this.lastMouseY) * this.rotationSpeed;

    if (this.isDragging) {
      // Update azimuth (horizontal rotation)
      this.currentAzimuthAngle += deltaX;

      // Update polar angle (vertical rotation) with constraints
      this.currentPolarAngle = Math.max(
        this.minPolarAngle,
        Math.min(this.maxPolarAngle, this.currentPolarAngle - deltaY)
      );

      this.updateCameraPosition();
    } else if (this.isPanning) {
      this.handlePan(deltaX, deltaY);
    }

    this.lastMouseX = event.clientX;
    this.lastMouseY = event.clientY;
  };

  private handleMouseUp = () => {
    this.isDragging = false;
    this.isPanning = false;
  };

  private handleWheel = (event: WheelEvent) => {
    event.preventDefault();
    const toTarget = vec3.sub(vec3.create(), this.position, this.target);
    const distance = vec3.length(toTarget);

    // Adjust zoom speed based on distance (slower when close)
    const adjustedZoomSpeed = this.zoomSpeed * (distance / 20);
    // Invert zoom direction
    const zoomFactor = 1.0 + Math.sign(event.deltaY) * adjustedZoomSpeed;

    const newDistance = Math.max(
      this.minDistance,
      Math.min(this.maxDistance, distance * zoomFactor)
    );
    vec3.scale(toTarget, toTarget, newDistance / distance);
    vec3.add(this.position, this.target, toTarget);
  };

  private handleKeyDown = (event: KeyboardEvent) => {
    switch (event.key.toLowerCase()) {
      case "f":
        this.setStandardView("front");
        break;
      case "t":
        this.setStandardView("top");
        break;
      case "s":
        this.setStandardView("side");
        break;
      case "r":
        this.setStandardView("reset");
        break;
    }
  };

  setStandardView(view: "front" | "top" | "side" | "reset") {
    switch (view) {
      case "front":
        this.currentPolarAngle = Math.PI / 2;
        this.currentAzimuthAngle = Math.PI; // 180° to face front from other side
        break;
      case "top":
        this.currentPolarAngle = 0.1;
        this.currentAzimuthAngle = Math.PI; // 180° to maintain orientation
        break;
      case "side":
        this.currentPolarAngle = Math.PI / 2;
        this.currentAzimuthAngle = -Math.PI / 2; // -90° for right side view from other side
        break;
      case "reset":
        // Reset to 45° view flipped around horizontal axis
        this.currentPolarAngle = Math.PI / 4;
        this.currentAzimuthAngle = (-Math.PI * 3) / 4;
        if (this.modelBounds) {
          this.target = vec3.clone(this.modelBounds[0]);
        }
        break;
    }
    this.updateCameraPosition();
  }

  getViewProjectionMatrix(): Float32Array {
    const viewMatrix = mat4.create();
    const projectionMatrix = mat4.create();
    const viewProjectionMatrix = mat4.create();

    mat4.lookAt(viewMatrix, this.position, this.target, this.up);

    if (this.isOrtho) {
      const scale = this.orthoScale;
      mat4.ortho(
        projectionMatrix,
        -scale * this.aspect,
        scale * this.aspect,
        -scale,
        scale,
        this.near,
        this.far
      );
    } else {
      mat4.perspective(
        projectionMatrix,
        this.fov,
        this.aspect,
        this.near,
        this.far
      );
    }

    mat4.multiply(viewProjectionMatrix, projectionMatrix, viewMatrix);
    return viewProjectionMatrix as Float32Array;
  }

  getNormalMatrix(): Float32Array {
    const normalMatrix = mat4.create();
    const viewMatrix = mat4.create();

    mat4.lookAt(viewMatrix, this.position, this.target, this.up);
    mat4.invert(normalMatrix, viewMatrix);
    mat4.transpose(normalMatrix, normalMatrix);

    return normalMatrix as Float32Array;
  }

  getPosition(): vec3 {
    return this.position;
  }

  setAspectRatio(aspect: number) {
    this.aspect = aspect;
  }
}
