import io
import time
from collections import OrderedDict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torchvision.models as tv_models
import torchvision.transforms as transforms
from django.conf import settings
from PIL import Image

MODEL_CACHE_SIZE = getattr(settings, "MODEL_CACHE_SIZE", 5)

_model_cache = OrderedDict()


def _get_torchvision_constructor(arch):
    CONSTRUCTORS = {
        "resnet18": tv_models.resnet18,
        "resnet34": tv_models.resnet34,
        "resnet50": tv_models.resnet50,
        "resnet101": tv_models.resnet101,
        "resnet152": tv_models.resnet152,
        "efficientnet_b0": tv_models.efficientnet_b0,
        "efficientnet_b1": tv_models.efficientnet_b1,
        "efficientnet_b2": tv_models.efficientnet_b2,
        "efficientnet_b3": tv_models.efficientnet_b3,
        "efficientnet_b4": tv_models.efficientnet_b4,
        "efficientnet_b5": tv_models.efficientnet_b5,
        "efficientnet_b6": tv_models.efficientnet_b6,
        "efficientnet_b7": tv_models.efficientnet_b7,
        "vgg16": tv_models.vgg16,
        "vgg19": tv_models.vgg19,
        "densenet121": tv_models.densenet121,
        "densenet169": tv_models.densenet169,
        "densenet201": tv_models.densenet201,
        "mobilenet_v2": tv_models.mobilenet_v2,
        "mobilenet_v3_small": tv_models.mobilenet_v3_small,
        "mobilenet_v3_large": tv_models.mobilenet_v3_large,
        "inception_v3": tv_models.inception_v3,
        "vit_b_16": tv_models.vit_b_16,
        "vit_b_32": tv_models.vit_b_32,
        "vit_l_16": tv_models.vit_l_16,
        "vit_l_32": tv_models.vit_l_32,
        "swin_t": tv_models.swin_t,
        "swin_s": tv_models.swin_s,
        "swin_b": tv_models.swin_b,
    }
    return CONSTRUCTORS.get(arch)


def _adjust_classifier(model, arch, num_classes):
    if arch.startswith("resnet") or arch == "inception_v3":
        model.fc = nn.Linear(model.fc.in_features, num_classes)
    elif arch.startswith("efficientnet"):
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)
    elif arch.startswith("vgg"):
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    elif arch.startswith("densenet"):
        model.classifier = nn.Linear(model.classifier.in_features, num_classes)
    elif arch.startswith("mobilenet"):
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    elif arch.startswith("vit"):
        model.heads.head = nn.Linear(model.heads.head.in_features, num_classes)
    elif arch.startswith("swin"):
        model.head = nn.Linear(model.head.in_features, num_classes)
    return model


def load_model(ml_model):
    cache_key = (ml_model.id, ml_model.model_version)
    if cache_key in _model_cache:
        _model_cache.move_to_end(cache_key)
        return _model_cache[cache_key]

    arch = ml_model.architecture
    num_classes = ml_model.num_classes
    model_path = ml_model.model_file.path

    if arch == "custom":
        safe_builtins = {
            k: v for k, v in __builtins__.items() if k in (
                "range", "len", "int", "float", "bool", "str", "list", "dict",
                "tuple", "set", "enumerate", "zip", "map", "filter", "sorted",
                "min", "max", "sum", "abs", "round", "isinstance", "issubclass",
                "hasattr", "getattr", "setattr", "type", "super", "property",
                "staticmethod", "classmethod", "True", "False", "None",
                "print", "ValueError", "TypeError", "RuntimeError",
            )
        } if isinstance(__builtins__, dict) else {}
        namespace = {"torch": torch, "nn": nn, "__builtins__": safe_builtins}
        exec(ml_model.custom_architecture_code, namespace)
        if "build_model" not in namespace:
            raise ValueError("Custom architecture code must define build_model(num_classes)")
        model = namespace["build_model"](num_classes)
    else:
        constructor = _get_torchvision_constructor(arch)
        if constructor is None:
            raise ValueError(f"Unknown architecture: {arch}")
        model = constructor(weights=None)
        model = _adjust_classifier(model, arch, num_classes)

    try:
        state_dict = torch.load(model_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state_dict)
    except Exception:
        model = torch.load(model_path, map_location="cpu", weights_only=False)

    model.eval()

    if len(_model_cache) >= MODEL_CACHE_SIZE:
        _model_cache.popitem(last=False)
    _model_cache[cache_key] = model
    return model


def preprocess_image(image_path, ml_model):
    path = Path(image_path)
    suffix = path.suffix.lower()

    if suffix == ".dcm":
        import pydicom
        ds = pydicom.dcmread(str(path))
        arr = ds.pixel_array.astype(np.float32)
        if arr.ndim == 2:
            arr = (arr - arr.min()) / (arr.max() - arr.min() + 1e-8) * 255
            img = Image.fromarray(arr.astype(np.uint8), mode="L")
        else:
            img = Image.fromarray(arr.astype(np.uint8))
    elif suffix in (".nii", ".gz"):
        import nibabel as nib
        nii = nib.load(str(path))
        data = np.array(nii.dataobj, dtype=np.float32)
        if data.ndim == 3:
            mid = data.shape[2] // 2
            sl = data[:, :, mid]
        else:
            sl = data
        sl = (sl - sl.min()) / (sl.max() - sl.min() + 1e-8) * 255
        img = Image.fromarray(sl.astype(np.uint8), mode="L")
    else:
        img = Image.open(image_path)

    channels = ml_model.input_channels
    if channels == 3:
        img = img.convert("RGB")
    elif channels == 1:
        img = img.convert("L")

    size = ml_model.input_size
    mean = ml_model.preprocessing_mean or [0.485, 0.456, 0.406]
    std = ml_model.preprocessing_std or [0.229, 0.224, 0.225]

    if channels == 1:
        mean = [mean[0]] if len(mean) > 1 else mean
        std = [std[0]] if len(std) > 1 else std

    transform = transforms.Compose([
        transforms.Resize((size, size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=mean, std=std),
    ])
    tensor = transform(img)
    return tensor.unsqueeze(0)


def run_inference(ml_model, image_path):
    start = time.time()
    model = load_model(ml_model)
    input_tensor = preprocess_image(image_path, ml_model)

    with torch.no_grad():
        output = model(input_tensor)
        if isinstance(output, tuple):
            output = output[0]

    probs = torch.softmax(output, dim=1).squeeze()
    confidence, predicted_idx = torch.max(probs, dim=0)
    predicted_idx = predicted_idx.item()
    confidence = confidence.item()

    labels = ml_model.class_labels
    elapsed_ms = int((time.time() - start) * 1000)

    probabilities = {}
    for i, label in enumerate(labels):
        probabilities[label] = round(probs[i].item(), 4)

    return {
        "predicted_class_index": predicted_idx,
        "predicted_label": labels[predicted_idx] if predicted_idx < len(labels) else f"Class {predicted_idx}",
        "confidence": round(confidence, 4),
        "probabilities": probabilities,
        "inference_time_ms": elapsed_ms,
    }


def _find_last_conv_layer(model):
    last_conv = None
    last_name = None
    for name, module in model.named_modules():
        if isinstance(module, (nn.Conv2d, nn.Conv1d)):
            last_conv = module
            last_name = name
    return last_conv, last_name


def _get_target_layer(model, ml_model):
    if ml_model.gradcam_target_layer:
        parts = ml_model.gradcam_target_layer.split(".")
        layer = model
        for p in parts:
            if p.isdigit():
                layer = layer[int(p)]
            else:
                layer = getattr(layer, p)
        return layer
    layer, _ = _find_last_conv_layer(model)
    return layer


def generate_gradcam(ml_model, image_path, predicted_class_index):
    if ml_model.architecture == "custom" and not ml_model.xai_script:
        return None

    model = load_model(ml_model)
    input_tensor = preprocess_image(image_path, ml_model)

    target_layer = _get_target_layer(model, ml_model)
    if target_layer is None:
        return None

    activations = []
    gradients = []

    def fwd_hook(module, inp, out):
        activations.append(out.detach())

    def bwd_hook(module, grad_in, grad_out):
        gradients.append(grad_out[0].detach())

    fwd_handle = target_layer.register_forward_hook(fwd_hook)
    bwd_handle = target_layer.register_full_backward_hook(bwd_hook)

    try:
        model.zero_grad()
        output = model(input_tensor)
        if isinstance(output, tuple):
            output = output[0]
        score = output[0, predicted_class_index]
        score.backward()

        act = activations[0].squeeze()
        grad = gradients[0].squeeze()

        weights = grad.mean(dim=(1, 2)) if grad.ndim == 3 else grad.mean(dim=-1)
        cam = torch.zeros(act.shape[1:], dtype=act.dtype)
        for i, w in enumerate(weights):
            cam += w * act[i]
        cam = torch.relu(cam)
        cam = cam - cam.min()
        if cam.max() > 0:
            cam = cam / cam.max()

        cam_np = cam.cpu().numpy()
        cam_resized = np.array(
            Image.fromarray((cam_np * 255).astype(np.uint8)).resize(
                (ml_model.input_size, ml_model.input_size), Image.BILINEAR
            )
        )

        import matplotlib.cm as cm
        heatmap = cm.jet(cam_resized / 255.0)[:, :, :3]
        heatmap = (heatmap * 255).astype(np.uint8)

        orig = Image.open(image_path).convert("RGB").resize(
            (ml_model.input_size, ml_model.input_size)
        )
        orig_np = np.array(orig)
        overlay = (0.5 * orig_np + 0.5 * heatmap).astype(np.uint8)
        return Image.fromarray(overlay)
    finally:
        fwd_handle.remove()
        bwd_handle.remove()
