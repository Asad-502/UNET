import argparse
import os
import torch
import torch.optim as optim
from tqdm import tqdm
from models import AM_U_Net, R2_AM_U_Net, init_weights
from dataset import RetinalDataset
from loss import JaccardLoss
from train_test import train, test
from torch.utils.data import DataLoader
from torchvision import transforms
import os
import random
import numpy as np
from math import floor
from sklearn.model_selection import train_test_split
from torch.utils.data import Subset

# Function to set random seeds for reproducibility
def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

# Argument parser
def parse_args():
    parser = argparse.ArgumentParser(description="Vessel Segmentation Training")
    
    parser.add_argument("--model", choices=["AM_U_Net", "R2_AM_U_Net"], required=True, help="Model architecture to use")
    parser.add_argument("--dataset", choices=["DRIVE", "STARE", "HRF", "CHASE"], required=True, help="Dataset to use for training")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size for training and testing")
    parser.add_argument("--learning_rate", type=float, default=0.001, help="Learning rate for the optimizer")
    parser.add_argument("--max_epochs", type=int, default=500, help="Maximum number of epochs for training")
    parser.add_argument("--patience", type=int, default=10, help="Patience for early stopping")
    parser.add_argument("--image_size", type=int, default=512, help="Size of the input images")
    parser.add_argument("--checkpoint", type=str, default=None, help="Path to the checkpoint file")
    parser.add_argument("--init_type", choices=["normal", "xavier", "kaiming", "orthogonal"], default="normal", help="Type of weight initialization")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")  # Added seed argument
    
    return parser.parse_args()

# Function to split the dataset
def split_dataset(dataset, train_ratio=0.7, seed=42):
    # Get the indices for the dataset
    indices = list(range(len(dataset)))
    
    # Split the indices into train and test sets (70% train, 30% test)
    train_indices, test_indices = train_test_split(indices, train_size=train_ratio, random_state=seed)

    # Create subset datasets
    train_dataset = Subset(dataset, train_indices)
    test_dataset = Subset(dataset, test_indices)
    
    return train_dataset, test_dataset

def main():
    # Parse arguments
    args = parse_args()

    # Set the random seed for reproducibility
    set_seed(args.seed)

    # Set the model based on the argument
    if args.model == "AM_U_Net":
        model = AM_U_Net()
    elif args.model == "R2_AM_U_Net":
        model = R2_AM_U_Net()

    # Apply the weight initialization function
    init_weights(model, init_type=args.init_type)

    transform = transforms.Compose([
        transforms.Resize((args.image_size, args.image_size)),
        transforms.ToTensor()
    ])

    # Determine the dataset paths based on the chosen dataset
    dataset_paths = {
        "DRIVE": {
            "image_dir": "/content/UNET/datasets/drive-digital-retinal-images/DRIVE/training/images",
            "mask_dir": "/content/UNET/datasets/drive-digital-retinal-images/DRIVE/training/1st_manual",
            "test_image_dir": "/content/UNET/datasets/drive-digital-retinal-images/DRIVE/test/images",
            "test_mask_dir": "/content/UNET/datasets/drive-digital-retinal-images/DRIVE/test/1st_manual"
        },
        "STARE": {
            "image_dir": "datasets/stare/training/images",
            "mask_dir": "datasets/stare/training/manual1",
            "test_image_dir": "datasets/stare/test/images",
            "test_mask_dir": "datasets/stare/test/mask"
        },
        "HRF": {
            "image_dir": "datasets/hrf/images",
            "mask_dir": "datasets/hrf/manual1",
            "test_image_dir": "datasets/hrf/test/images",
            "test_mask_dir": "datasets/hrf/test/mask"
        },
        "CHASE": {
            "image_dir": "datasets/chase",
            "mask_dir": "datasets/chase",
            "test_image_dir": "datasets/chase/test/images",
            "test_mask_dir": "datasets/chase/test/mask"
        }
    }

    # Create datasets using the provided paths for the chosen dataset
    train_dataset = RetinalDataset(dataset_type=args.dataset,
                                   image_dir=dataset_paths[args.dataset]["image_dir"],
                                   mask_dir=dataset_paths[args.dataset]["mask_dir"],
                                   transform=transform)

    # Perform the split
    train_dataset, test_dataset = split_dataset(train_dataset, train_ratio=0.7, seed=args.seed)

    # Now `train_dataset` and `test_dataset` contain 70% and 30% of the images, respectively
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=False)

    # Criterion and optimizer
    criterion = JaccardLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.learning_rate)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    # Initialize variables for early stopping and checkpointing
    best_loss = float('inf')
    counter = 0
    start_epoch = 0

    # Load checkpoint if it exists
    if args.checkpoint and os.path.isfile(args.checkpoint):
        print(f"Loading checkpoint from {args.checkpoint}")
        checkpoint = torch.load(args.checkpoint)
        model.load_state_dict(checkpoint['model_state_dict'])
        optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        best_loss = checkpoint.get('best_loss', float('inf'))
        counter = checkpoint.get('counter', 0)
        start_epoch = checkpoint.get('epoch', 0)
        print(f"Resuming training from epoch {start_epoch + 1}")

    # Training the model with early stopping
    for epoch in range(start_epoch, args.max_epochs):  # Max number of epochs
        print(f"Epoch {epoch + 1}")
        train(model, train_loader, criterion, optimizer, device)
        val_loss = test(model, test_loader, criterion, device)
        
        # Early stopping check
        if val_loss < best_loss:
            best_loss = val_loss
            counter = 0
            # Save the best model with the model name as the checkpoint name
            torch.save({
            'epoch': epoch + 1,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'best_loss': best_loss,
            'counter': counter,
            }, f"./weights/{args.model}_{args.dataset}_best_model.pth")
            print("Model improved, saving...")
        else:
            counter += 1
            print(f"No improvement. Early stopping counter: {counter}/{args.patience}")
            if counter >= args.patience:
                print("Early stopping triggered. Training stopped.")
                break

    # Save checkpoint
    torch.save({
        'epoch': epoch + 1,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'best_loss': best_loss,
        'counter': counter,
    }, f"./weights/{args.model}_{args.dataset}_last_model.pth")

if __name__ == "__main__":
    main()
