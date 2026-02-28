import torch
import torch.nn as nn
import numpy as np
from typing import Optional, List, Union
import os

from models.text_encoder import TextEncoder
from models.diffusion import PixelDiffusionUNet
from models.decoder import PixelArtDecoder


class PixelArtGenerator(nn.Module):
    def __init__(
        self,
        device: str = "cuda",
        image_size: int = 64,
        num_timesteps: int = 1000,
        clip_model: str = "openai/clip-vit-base-patch32"
    ):
        super().__init__()
        self.device = device
        self.image_size = image_size
        self.num_timesteps = num_timesteps
        
        self.text_encoder = TextEncoder(model_name=clip_model, device=device)
        self.unet = PixelDiffusionUNet(in_channels=3, out_channels=3).to(device)
        self.decoder = PixelArtDecoder(latent_dim=512, image_size=image_size).to(device)
        
        self.betas = self._cosine_beta_schedule(num_timesteps).to(device)
        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = torch.cumprod(self.alphas, dim=0)
    
    def _cosine_beta_schedule(self, timesteps: int, s: float = 0.008) -> torch.Tensor:
        steps = timesteps + 1
        x = torch.linspace(0, timesteps, steps)
        alphas_cumprod = torch.cos(((x / timesteps) + s) / (1 + s) * torch.pi * 0.5) ** 2
        alphas_cumprod = alphas_cumprod / alphas_cumprod[0]
        betas = 1 - (alphas_cumprod[1:] / alphas_cumprod[:-1])
        return torch.clip(betas, 0, 0.999)
    
    def forward_diffusion(self, x0: torch.Tensor, t: torch.Tensor) -> tuple:
        noise = torch.randn_like(x0)
        alpha_t = self.alphas_cumprod[t][:, None, None, None]
        xt = torch.sqrt(alpha_t) * x0 + torch.sqrt(1 - alpha_t) * noise
        return xt, noise
    
    @torch.no_grad()
    def reverse_diffusion(self, text_embedding: torch.Tensor, num_steps: int = 50) -> torch.Tensor:
        xt = torch.randn(1, 3, self.image_size, self.image_size, device=self.device)
        
        step_indices = torch.linspace(self.num_timesteps - 1, 0, num_steps, dtype=torch.long, device=self.device)
        
        for i, t in enumerate(step_indices):
            t_batch = t.expand(xt.shape[0])
            
            predicted_noise = self.unet(xt, t_batch)
            
            alpha_t = self.alphas_cumprod[t]
            alpha_t_prev = self.alphas_cumprod[max(t - 1, 0)]
            
            coef1 = 1 / torch.sqrt(alpha_t)
            coef2 = (1 - alpha_t) / torch.sqrt(1 - alpha_t)
            
            xt = coef1 * (xt - coef2 * predicted_noise)
            
            if t > 0:
                noise = torch.randn_like(xt)
                sigma = torch.sqrt(self.betas[t])
                xt = xt + sigma * noise
        
        return xt
    
    def generate(
        self,
        text: str,
        num_steps: int = 50,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None
    ) -> torch.Tensor:
        if seed is not None:
            torch.manual_seed(seed)
        
        text_embedding = self.text_encoder.encode(text)
        
        latent = self.reverse_diffusion(text_embedding, num_steps)
        
        pixel_image = self.decoder(latent.flatten(1))
        
        return pixel_image
    
    def generate_batch(
        self,
        texts: List[str],
        num_steps: int = 50,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None
    ) -> List[torch.Tensor]:
        results = []
        for text in texts:
            image = self.generate(text, num_steps, guidance_scale, seed)
            results.append(image)
        return results
    
    def save_image(self, tensor: torch.Tensor, path: str):
        from PIL import Image
        
        image = tensor.squeeze(0).cpu()
        image = (image + 1) / 2
        image = (image * 255).clamp(0, 255).byte()
        image = image.permute(1, 2, 0).numpy()
        
        img = Image.fromarray(image)
        img.save(path)
    
    def save_pretrained(self, path: str):
        os.makedirs(path, exist_ok=True)
        torch.save({
            "unet": self.unet.state_dict(),
            "decoder": self.decoder.state_dict(),
            "config": {
                "image_size": self.image_size,
                "num_timesteps": self.num_timesteps
            }
        }, os.path.join(path, "model.pt"))
    
    def load_pretrained(self, path: str):
        checkpoint = torch.load(os.path.join(path, "model.pt"), map_location=self.device)
        self.unet.load_state_dict(checkpoint["unet"])
        self.decoder.load_state_dict(checkpoint["decoder"])
        return self


def create_pixel_art_generator(device: str = "cuda", **kwargs) -> PixelArtGenerator:
    return PixelArtGenerator(device=device, **kwargs)


if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"使用设备: {device}")
    
    generator = create_pixel_art_generator(device=device, image_size=64)
    
    prompt = "a cute pixel art cat sitting on a tree"
    print(f"生成提示词: {prompt}")
    
    image = generator.generate(prompt, num_steps=50, seed=42)
    print(f"生成图像形状: {image.shape}")
    
    generator.save_image(image, "output_pixel_cat.png")
    print("图像已保存到 output_pixel_cat.png")
