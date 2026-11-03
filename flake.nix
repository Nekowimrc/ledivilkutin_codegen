{
  description = "A dev environment for Ledivilkutin code generation";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
      };
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          # basic utilities
          bashInteractive
          coreutils
          git

          # for nix development
          nixpkgs-fmt

          # Python and mcp package
          (python3.withPackages (
            ps: with ps; [
              black
              pytest
            ]
          ))
        ];

      };
    };
}
